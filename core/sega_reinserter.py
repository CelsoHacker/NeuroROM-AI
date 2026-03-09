# NeuroROM AI - Sega Master System Reinserter
# v6.1 (automap + repoint-safe bank0 + HUD trunc)

from __future__ import annotations

import json
import os
import re
import shutil
import hashlib
import textwrap
import unicodedata
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
except Exception:
    requests = None

from utils.rom_io import (
    atomic_write_bytes,
    compute_checksums,
    ensure_parent_dir,
    make_backup,
)
try:
    from core.final_qa import evaluate_reinsertion_qa, write_qa_artifacts
except Exception:
    try:
        from final_qa import evaluate_reinsertion_qa, write_qa_artifacts
    except Exception:
        evaluate_reinsertion_qa = None
        write_qa_artifacts = None

try:
    from core.qa_gate_runtime import (
        run_qa_gate as run_qa_gate_runtime,
        run_runtime_coverage as run_runtime_coverage_runtime,
        discover_runtime_evidence_path as discover_runtime_evidence_path_runtime,
    )
except Exception:
    try:
        from qa_gate_runtime import (
            run_qa_gate as run_qa_gate_runtime,
            run_runtime_coverage as run_runtime_coverage_runtime,
            discover_runtime_evidence_path as discover_runtime_evidence_path_runtime,
        )
    except Exception:
        run_qa_gate_runtime = None
        run_runtime_coverage_runtime = None
        discover_runtime_evidence_path_runtime = None

try:
    # Execução como pacote (GUI principal).
    from core.sms_game_engineering import SMSGameEngineeringManager
except Exception:
    try:
        # Execução direta.
        from sms_game_engineering import SMSGameEngineeringManager
    except Exception:
        SMSGameEngineeringManager = None

try:
    from core.sms_post_reinsertion import apply_sms_post_reinsertion_patches, PostPatchError
except Exception:
    try:
        from sms_post_reinsertion import apply_sms_post_reinsertion_patches, PostPatchError
    except Exception:
        apply_sms_post_reinsertion_patches = None
        PostPatchError = RuntimeError

try:
    from universal_kit.multi_decompress import MultiDecompress, CompressionAlgorithm
    from universal_kit.multi_compress import MultiCompress
except Exception:
    MultiDecompress = None
    CompressionAlgorithm = None
    MultiCompress = None

try:
    from core.compression_detector import CompressionDetector
except Exception:
    try:
        from compression_detector import CompressionDetector
    except Exception:
        CompressionDetector = None

try:
    from universal_kit.endian_pointer_hunter import EndianPointerHunter
except Exception:
    EndianPointerHunter = None

try:
    from plugins.plugin_registry import get_plugin_for_rom as _get_plugin_for_rom
except Exception:
    _get_plugin_for_rom = None

try:
    from core.sms_glyph_injector import SMSGlyphInjector
except Exception:
    try:
        from sms_glyph_injector import SMSGlyphInjector
    except Exception:
        SMSGlyphInjector = None

try:
    from core.compact_glossary import apply_compact_glossary
except Exception:
    try:
        from compact_glossary import apply_compact_glossary
    except Exception:
        def apply_compact_glossary(text: str, crc32: str = None) -> str:
            return str(text or "")

DEBUG = os.environ.get("NEUROROM_DEBUG_REINSERT", "0") == "1"


def strip_accents_for_rom(text: str) -> str:
    """Remove diacríticos para ROMs com fonte sem suporte a acentos."""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


@dataclass
class MapEntry:
    key: str
    offset: int
    max_len: int
    raw_len: Optional[int]
    category: str
    has_pointer: bool
    pointer_offsets: List[int]
    pointer_refs: List[Dict[str, Any]]
    terminator: Optional[int]
    encoding: str
    reinsertion_safe: bool = True
    blocked_reason: Optional[str] = None


class ReinsertionError(Exception):
    pass


class SegaMasterSystemReinserter:
    """Reinsere textos no ROM com 3 regras:

    [OK] repointed  -> se tem pointer_offsets e conseguimos atualizar ponteiros com segurança
    [BLOCKED]       -> sem ponteiros (endereço fixo)
    [TRUNC] HUD     -> permite truncar se categoria == HUD
    """

    BANK0_LIMIT = 0x4000
    PT_HINT_WORDS = {
        "de", "da", "do", "das", "dos", "e", "que", "para", "com", "sem", "por", "em",
        "na", "no", "nas", "nos", "um", "uma", "voce", "voces", "nao", "sim", "salvar",
        "carregar", "ataque", "defesa", "magia", "chave", "chaves", "norte", "sul", "leste",
        "oeste", "vida", "item", "itens", "comprar", "vender", "ouro", "voltar", "entrar",
        "sair", "falar", "usar", "pronto", "acampar", "cura", "forca", "inteligencia",
        "eu", "ele", "ela", "nos", "nossa", "nosso", "minha", "meu", "seu", "sua",
        "tenho", "tem", "tens", "somos", "estou", "esta", "estao", "diz", "disse",
        "obrigado", "obrigada", "voce", "voces", "ola", "bem", "mal", "aqui", "ali",
        "agora", "depois", "antes", "hoje", "amanha", "ontem", "mundo", "cidade",
        "casa", "porta", "caminho", "ponte", "rio", "montanha", "ilha", "reino",
        "som", "luz", "parece", "custar", "dobrar", "o", "a", "os", "as", "tu", "vos",
        "vós", "te", "seu", "sua", "grande", "abismo", "virtude", "humildade", "vaidade",
        "musica", "música", "voz", "pergunta", "terra", "chao", "chão", "salgueiro",
        "poderoso", "preco", "preço", "justo", "acenda", "vela", "carruagem", "guerreiros",
        "retorno", "suposto", "assassinato", "filosofias", "verdade", "coragem", "amor",
        "estranho", "estranha", "antigo", "antiga", "livro", "mapa", "artefatos", "frio",
        "ventos", "moderado", "cama", "negocio", "negócio", "obrigatorio", "obrigatório",
        "concentra", "seus", "pensamentos", "nesse", "assunto", "trouxe", "paz", "profunda",
        "galhos", "ondulantes", "profundeza", "algumas", "crepusculo", "crepúsculo", "reune",
        "reúne", "enfim", "muito", "tempo", "sobe", "pode", "visto", "pela", "sobre",
        "quer", "ver", "meus", "produtos", "produto", "mostrar", "gostar", "gostaria",
        "qual", "sera", "teu", "nome", "escudo", "homem", "mulher", "novo", "jogo",
        "opcoes", "opcao", "continuar",
        "es", "masc", "femin",
    }
    EN_HINT_WORDS = {
        "the", "and", "you", "your", "with", "without", "for", "from", "to", "of", "in",
        "on", "is", "are", "this", "that", "have", "has", "will", "can", "cannot", "north",
        "south", "east", "west", "save", "load", "attack", "defense", "magic", "item",
        "items", "key", "keys", "shop", "buy", "sell", "friend", "hello", "yes", "no",
    }
    EN_STOPWORDS_GATE = {
        "the", "you", "then", "this", "there", "that", "with", "from", "into",
        "your", "have", "will", "would", "should", "could", "what", "where",
        "when", "why", "how", "who", "which", "only", "here", "there", "these",
        "thou", "thee", "thy", "thine", "hast", "hath", "dost", "doth", "shalt", "ye",
        "says", "she", "consider", "but", "very", "really", "read", "book", "history",
        "pick", "small", "room", "stay", "costs",
    }
    EN_TO_PT_WORDS = {
        "name": "nome",
        "job": "classe",
        "health": "vida",
        "male": "masc",
        "female": "femin",
        "or": "ou",
        "wind": "vento",
        "winds": "ventos",
        "north": "norte",
        "south": "sul",
        "east": "leste",
        "west": "oeste",
        "up": "cima",
        "down": "baixo",
        "save": "salvar",
        "load": "carregar",
        "camp": "acampar",
        "ready": "pronto",
        "items": "itens",
        "item": "item",
        "weapon": "arma",
        "weapons": "armas",
        "key": "chave",
        "keys": "chaves",
        "magic": "magia",
        "fire": "fogo",
        "sleep": "sono",
        "stone": "pedra",
        "lightning": "raio",
        "talk": "falar",
        "run": "correr",
        "rest": "descansar",
        "attack": "ataque",
        "defense": "defesa",
        "shop": "loja",
        "buy": "comprar",
        "sell": "vender",
        "honesty": "honestidade",
        "compassion": "compaixão",
        "justice": "justiça",
        "sacrifice": "sacrifício",
        "honor": "honra",
        "spirituality": "espiritualidade",
        "humility": "humildade",
        "castle": "castelo",
        "moonglow": "luarluz",
        "options": "opções",
        "gold": "ouro",
        "hello": "ola",
        "friend": "amigo",
        "yes": "sim",
        "no": "não",
        "rune": "runa",
    }
    PT_ABBREVIATIONS = {
        "voce": "vc",
        "voces": "vcs",
        "senhor": "sr",
        "senhora": "sra",
        "senhores": "srs",
        "nao": "nao",
        "para": "p/",
        "porque": "pq",
        "com": "c/",
        "sem": "s/",
        "magia": "mag",
        "magico": "mag",
        "magica": "mag",
        "armadura": "arm",
        "espada": "esp",
        "ataque": "atq",
        "defesa": "def",
        "inteligencia": "int",
        "forca": "for",
        "agilidade": "agi",
        "vitalidade": "vit",
        "experiencia": "exp",
        "pontos": "pts",
        "ponto": "pt",
        "numero": "num",
        "numeros": "nums",
        "nivel": "niv",
        "opcoes": "opc.",
        "opções": "opc.",
        "opcao": "opc.",
        "opção": "opc.",
        "inventario": "inv.",
        "inventário": "inv.",
        "equipamento": "equip.",
        "equipamentos": "equips.",
        "configuracao": "conf.",
        "configuração": "conf.",
        "selecao": "sel.",
        "seleção": "sel.",
        "selecionar": "selec.",
        "direcao": "dir.",
        "direção": "dir.",
        "habilidade": "hab.",
        "habilidades": "habs.",
        "masculino": "masc.",
        "feminino": "fem.",
        "andar": "andar",
        "andar.": "and.",
        "andar,": "and,",
    }
    SHORT_STYLE_MAP = {
        "opcoes": "opc.",
        "opcao": "opc.",
        "inventario": "inv.",
        "equipamento": "equip.",
        "equipamentos": "equips.",
        "configuracao": "conf.",
        "selecao": "sel.",
        "selecionar": "selec.",
        "direcao": "dir.",
        "habilidade": "hab.",
        "habilidades": "habs.",
        "masculino": "masc.",
        "feminino": "fem.",
        "continuar": "cont.",
        "espiritualidade": "espirit.",
        "compreensao": "comp.",
    }
    PT_DROP_WORDS = {
        "a", "o", "as", "os", "de", "da", "do", "das", "dos", "um", "uma", "uns", "umas",
        "e", "que", "com", "para", "por", "em", "na", "no", "nas", "nos",
        "the", "a", "an", "of", "to", "for", "in", "on", "at", "and",
    }
    DELTA_ISSUE_CATEGORIES = (
        "unchanged_equal_src",
        "suspicious_non_pt",
        "rom_vs_translated_mismatch",
        "placeholder_fail",
        "terminator_missing",
    )
    PLATFORM_BY_EXT = {
        ".sms": "SMS",
        ".gg": "SMS",
        ".bin": "MEGADRIVE",
        ".md": "MEGADRIVE",
        ".gen": "MEGADRIVE",
        ".smd": "MEGADRIVE",
        ".smc": "SNES",
        ".sfc": "SNES",
        ".swc": "SNES",
        ".fig": "SNES",
        ".nes": "NES",
        ".gba": "GBA",
        ".z64": "N64",
        ".n64": "N64",
        ".v64": "N64",
        ".psx": "PS1",
        ".iso": "PS1",
        ".cue": "PS1",
    }
    PLATFORM_DIALOG_DEFAULTS = {
        "SMS": {"width": 28, "lines": 4, "max_lines_hard": 8},
        "SNES": {"width": 30, "lines": 4, "max_lines_hard": 8},
        "NES": {"width": 30, "lines": 4, "max_lines_hard": 8},
        "MEGADRIVE": {"width": 30, "lines": 4, "max_lines_hard": 8},
        "GBA": {"width": 32, "lines": 4, "max_lines_hard": 10},
        "N64": {"width": 36, "lines": 5, "max_lines_hard": 12},
        "PS1": {"width": 36, "lines": 5, "max_lines_hard": 12},
    }
    COMPRESSION_PROFILE_BY_PLATFORM = {
        "SMS": ["RLE"],
        "MEGADRIVE": ["LZSS", "RLE"],
        "MD": ["LZSS", "RLE"],
        "NES": ["RLE"],
        "SNES": ["LZ77", "HUFFMAN", "RLE"],
        "GB": ["LZ77"],
        "GBA": ["LZ10", "HUFFMAN", "RLE"],
        "N64": ["MIO0", "YAY0", "YAZ0"],
        "PS1": ["LZSS", "BPE", "STR", "BIN"],
    }
    COMPRESSION_ALIASES = {
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
        "MIO0": "MIO0",
        "YAY0": "YAY0",
        "YAZ0": "YAZ0",
        "BPE": "BPE",
        "PSX_BPE": "BPE",
        "STR": "STR",
        "BIN": "BIN",
    }
    DEFAULT_RUNTIME_POLICY = {
        "normalize_nfc": True,
        "tilemap_require_tbl": True,
        "tilemap_fail_fast_without_tbl": True,
        "require_tilemap": True,
        "auto_relocate_if_needed": True,
        "strict_crc_safe_mode": False,
        "strict_crc_safe_mode_target_crc32": "DE9F8517",
        "auto_generate_diff_ranges": True,
        "auto_generate_diff_ranges_overwrite": False,
        "diff_ranges_margin_start": 2,
        "diff_ranges_margin_end": 16,
        "diff_ranges_merge_gap": 16,
        "custom_dictionary": "custom_dict.json",
        "apply_custom_dict_first": True,
        "translation_api_fallback": True,
        "translation_service": "google",
        "translation_api_timeout": 8,
        "translation_api_max_chars": 600,
        "translation_api_target_lang": "pt-BR",
        "translation_api_source_lang": "en",
        "glyph_injection_enabled": True,
        "glyph_font": "Verdana.ttf",
        "id_override_enabled": True,
        "id_override_file": "curated_fixes.json",
    }
    PLATFORM_STOPWORDS_EXTRA = {
        "SMS": {
            "thou",
            "thee",
            "thy",
            "thine",
            "shalt",
            "hast",
            "hath",
            "dost",
            "doth",
            "unto",
            "upon",
            "whilst",
            "ye",
        },
        "SNES": {
            "thou",
            "thee",
            "thy",
            "thine",
            "shalt",
            "hast",
            "hath",
            "dost",
            "doth",
            "unto",
            "upon",
            "whilst",
            "ye",
        }
    }
    PLATFORM_GLOSSARY_EXTRA = {
        "SMS": {
            "thou": "tu",
            "thee": "te",
            "thy": "teu",
            "thine": "teu",
            "shalt": "deves",
            "hast": "tens",
            "hath": "tem",
            "art": "es",
            "dost": "fazes",
            "doth": "faz",
            "ye": "vos",
            "unto": "a",
            "upon": "sobre",
            "whilst": "enquanto",
            "male": "masc",
            "female": "femin",
        },
        "SNES": {
            "thou": "tu",
            "thee": "te",
            "thy": "teu",
            "thine": "teu",
            "shalt": "deves",
            "hast": "tens",
            "hath": "tem",
            "art": "es",
            "dost": "fazes",
            "doth": "faz",
            "ye": "vos",
            "unto": "a",
            "upon": "sobre",
            "whilst": "enquanto",
            "male": "masc",
            "female": "femin",
        }
    }
    PLATFORM_HINTS_EXTRA = {
        "SMS": {
            "thou",
            "thee",
            "thy",
            "thine",
            "shalt",
            "hast",
            "hath",
            "dost",
            "doth",
            "ye",
            "unto",
            "upon",
            "whilst",
        },
        "SNES": {
            "thou",
            "thee",
            "thy",
            "thine",
            "shalt",
            "hast",
            "hath",
            "dost",
            "doth",
            "ye",
            "unto",
            "upon",
            "whilst",
        }
    }

    def __init__(self):
        self.mapping: Dict[str, MapEntry] = {}
        self.mapping_crc32: Optional[str] = None
        self._tbl_loader = None
        self._tile_entry_len: int = 1
        self._tile_space_seq: Optional[bytes] = None
        self._token_re = re.compile(r"(\{[^}]+\}|\[[^\]]+\]|<[^>]+>)")
        self._byte_placeholder_re = re.compile(r"\{B:([0-9A-Fa-f]{2})\}")
        self._word_re = re.compile(r"[A-Za-zÀ-ÿ0-9']+")
        self._strict_ptbr_mode = os.environ.get("NEUROROM_STRICT_PTBR", "0") == "1"
        self._strict_ptbr_changes: int = 0
        self._game_engineering_manager = None
        self._game_engineering_profile: Dict[str, Any] = {}
        self._game_engineering_profile_summary: Dict[str, Any] = {}
        self._game_engineering_text_changes: int = 0
        self._target_platform: str = "SMS"
        self._pt_hint_words = set(self.PT_HINT_WORDS)
        self._en_hint_words = set(self.EN_HINT_WORDS)
        self._en_stopwords_gate = set(self.EN_STOPWORDS_GATE)
        self._en_to_pt_words = dict(self.EN_TO_PT_WORDS)
        self._translation_runtime_policy = self._load_translation_runtime_policy()
        self._custom_dictionary: Dict[str, str] = {}
        self._custom_dict_word_map: Dict[str, str] = {}
        self._custom_dict_phrase_items: List[Tuple[str, str]] = []
        self._api_fallback_cache: Dict[str, str] = {}
        self._api_fallback_calls: int = 0
        self._api_fallback_success: int = 0
        self._api_fallback_rewrites: int = 0
        self._custom_dict_rewrites: int = 0
        self._custom_dict_path: Optional[str] = None
        self._detected_compressed_regions: List[Dict[str, Any]] = []
        self._apply_platform_overrides("SMS")
        self._load_custom_dictionary_runtime()
        if SMSGameEngineeringManager is not None:
            try:
                self._game_engineering_manager = SMSGameEngineeringManager()
            except Exception:
                self._game_engineering_manager = None

    def _project_root_dir(self) -> Path:
        """Resolve raiz do projeto a partir do módulo core."""
        return Path(__file__).resolve().parent.parent

    def _coerce_bool(self, value: Any, default: bool = False) -> bool:
        """Converte valor arbitrário para bool de forma estável."""
        if isinstance(value, bool):
            return value
        if value is None:
            return bool(default)
        txt = str(value).strip().lower()
        if txt in {"1", "true", "yes", "on", "sim", "s"}:
            return True
        if txt in {"0", "false", "no", "off", "nao", "não", "n"}:
            return False
        return bool(default)

    def _load_translation_runtime_policy(self) -> Dict[str, Any]:
        """
        Carrega política global de tradução/reinserção.
        Fonte principal: interface/translator_config.json.
        """
        policy = dict(self.DEFAULT_RUNTIME_POLICY)
        project_dir = self._project_root_dir()
        cfg_candidates = [
            project_dir / "interface" / "translator_config.json",
            project_dir / "translator_config.json",
        ]
        for cfg_path in cfg_candidates:
            if not cfg_path.exists():
                continue
            try:
                raw = json.loads(cfg_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(raw, dict):
                continue
            for key in (
                "normalize_nfc",
                "tilemap_require_tbl",
                "tilemap_fail_fast_without_tbl",
                "require_tilemap",
                "auto_relocate_if_needed",
                "strict_crc_safe_mode",
                "strict_crc_safe_mode_target_crc32",
                "auto_generate_diff_ranges",
                "auto_generate_diff_ranges_overwrite",
                "diff_ranges_margin_start",
                "diff_ranges_margin_end",
                "diff_ranges_merge_gap",
                "custom_dictionary",
                "apply_custom_dict_first",
                "translation_api_fallback",
                "translation_service",
                "translation_api_timeout",
                "translation_api_max_chars",
                "translation_api_target_lang",
                "translation_api_source_lang",
                "translation_api_url",
                "translation_api_key",
                "translation_api_region",
                "glyph_injection_enabled",
                "glyph_font",
                "id_override_enabled",
                "id_override_file",
            ):
                if key in raw:
                    policy[key] = raw.get(key)
            # Compat: require_tilemap atua como alias explícito de tilemap_require_tbl.
            if "require_tilemap" in raw and "tilemap_require_tbl" not in raw:
                policy["tilemap_require_tbl"] = raw.get("require_tilemap")
            break

        # Overrides por variável de ambiente para automação CI/pipeline.
        if os.environ.get("NEUROROM_FORCE_NFC") is not None:
            policy["normalize_nfc"] = self._coerce_bool(
                os.environ.get("NEUROROM_FORCE_NFC"), True
            )
        if os.environ.get("NEUROROM_TILEMAP_REQUIRE_TBL") is not None:
            policy["tilemap_require_tbl"] = self._coerce_bool(
                os.environ.get("NEUROROM_TILEMAP_REQUIRE_TBL"), True
            )
            policy["require_tilemap"] = policy["tilemap_require_tbl"]
        if os.environ.get("NEUROROM_TILEMAP_FAIL_FAST") is not None:
            policy["tilemap_fail_fast_without_tbl"] = self._coerce_bool(
                os.environ.get("NEUROROM_TILEMAP_FAIL_FAST"), True
            )
        if os.environ.get("NEUROROM_AUTO_RELOCATE_IF_NEEDED") is not None:
            policy["auto_relocate_if_needed"] = self._coerce_bool(
                os.environ.get("NEUROROM_AUTO_RELOCATE_IF_NEEDED"), True
            )
        if os.environ.get("NEUROROM_AUTO_RELOCATE") is not None:
            policy["auto_relocate_if_needed"] = self._coerce_bool(
                os.environ.get("NEUROROM_AUTO_RELOCATE"), True
            )
        if os.environ.get("NEUROROM_STRICT_CRC_SAFE_MODE") is not None:
            policy["strict_crc_safe_mode"] = self._coerce_bool(
                os.environ.get("NEUROROM_STRICT_CRC_SAFE_MODE"), False
            )
        if os.environ.get("NEUROROM_STRICT_CRC_SAFE_TARGET"):
            policy["strict_crc_safe_mode_target_crc32"] = str(
                os.environ.get("NEUROROM_STRICT_CRC_SAFE_TARGET")
            )
        if os.environ.get("NEUROROM_AUTO_GENERATE_DIFF_RANGES") is not None:
            policy["auto_generate_diff_ranges"] = self._coerce_bool(
                os.environ.get("NEUROROM_AUTO_GENERATE_DIFF_RANGES"),
                True,
            )
        if os.environ.get("NEUROROM_AUTO_GENERATE_DIFF_RANGES_OVERWRITE") is not None:
            policy["auto_generate_diff_ranges_overwrite"] = self._coerce_bool(
                os.environ.get("NEUROROM_AUTO_GENERATE_DIFF_RANGES_OVERWRITE"),
                False,
            )
        if os.environ.get("NEUROROM_DIFF_RANGES_MARGIN_START") is not None:
            policy["diff_ranges_margin_start"] = self._parse_int_value(
                os.environ.get("NEUROROM_DIFF_RANGES_MARGIN_START"),
                default=2,
            )
        if os.environ.get("NEUROROM_DIFF_RANGES_MARGIN_END") is not None:
            policy["diff_ranges_margin_end"] = self._parse_int_value(
                os.environ.get("NEUROROM_DIFF_RANGES_MARGIN_END"),
                default=16,
            )
        if os.environ.get("NEUROROM_DIFF_RANGES_MERGE_GAP") is not None:
            policy["diff_ranges_merge_gap"] = self._parse_int_value(
                os.environ.get("NEUROROM_DIFF_RANGES_MERGE_GAP"),
                default=16,
            )
        if os.environ.get("NEUROROM_TRANSLATION_API_FALLBACK") is not None:
            policy["translation_api_fallback"] = self._coerce_bool(
                os.environ.get("NEUROROM_TRANSLATION_API_FALLBACK"), True
            )
        if os.environ.get("NEUROROM_TRANSLATION_SERVICE"):
            policy["translation_service"] = os.environ.get("NEUROROM_TRANSLATION_SERVICE")
        if os.environ.get("NEUROROM_TRANSLATION_API_MAX_CHARS") is not None:
            policy["translation_api_max_chars"] = self._parse_int_value(
                os.environ.get("NEUROROM_TRANSLATION_API_MAX_CHARS"),
                default=600,
            )
        if os.environ.get("NEUROROM_CUSTOM_DICT_PATH"):
            policy["custom_dictionary"] = os.environ.get("NEUROROM_CUSTOM_DICT_PATH")
        if os.environ.get("NEUROROM_GLYPH_FONT"):
            policy["glyph_font"] = os.environ.get("NEUROROM_GLYPH_FONT")
        if os.environ.get("NEUROROM_GLYPH_INJECTION") is not None:
            policy["glyph_injection_enabled"] = self._coerce_bool(
                os.environ.get("NEUROROM_GLYPH_INJECTION"),
                True,
            )
        if os.environ.get("NEUROROM_ID_OVERRIDE_ENABLED") is not None:
            policy["id_override_enabled"] = self._coerce_bool(
                os.environ.get("NEUROROM_ID_OVERRIDE_ENABLED"),
                True,
            )
        if os.environ.get("NEUROROM_ID_OVERRIDE_FILE"):
            policy["id_override_file"] = os.environ.get("NEUROROM_ID_OVERRIDE_FILE")

        policy["tilemap_require_tbl"] = self._coerce_bool(
            policy.get("tilemap_require_tbl", policy.get("require_tilemap", True)),
            True,
        )
        policy["require_tilemap"] = bool(policy["tilemap_require_tbl"])
        policy["tilemap_fail_fast_without_tbl"] = self._coerce_bool(
            policy.get("tilemap_fail_fast_without_tbl", True),
            True,
        )
        policy["auto_relocate_if_needed"] = self._coerce_bool(
            policy.get("auto_relocate_if_needed", True),
            True,
        )
        policy["strict_crc_safe_mode"] = self._coerce_bool(
            policy.get("strict_crc_safe_mode", False),
            False,
        )
        policy["strict_crc_safe_mode_target_crc32"] = str(
            policy.get("strict_crc_safe_mode_target_crc32", "DE9F8517") or "DE9F8517"
        ).strip().upper()
        policy["auto_generate_diff_ranges"] = self._coerce_bool(
            policy.get("auto_generate_diff_ranges", True),
            True,
        )
        policy["auto_generate_diff_ranges_overwrite"] = self._coerce_bool(
            policy.get("auto_generate_diff_ranges_overwrite", False),
            False,
        )
        policy["diff_ranges_margin_start"] = max(
            0,
            int(self._parse_int_value(policy.get("diff_ranges_margin_start", 2), default=2)),
        )
        policy["diff_ranges_margin_end"] = max(
            0,
            int(self._parse_int_value(policy.get("diff_ranges_margin_end", 16), default=16)),
        )
        policy["diff_ranges_merge_gap"] = max(
            0,
            int(self._parse_int_value(policy.get("diff_ranges_merge_gap", 16), default=16)),
        )
        policy["normalize_nfc"] = self._coerce_bool(
            policy.get("normalize_nfc", True),
            True,
        )
        policy["translation_api_fallback"] = self._coerce_bool(
            policy.get("translation_api_fallback", True),
            True,
        )
        policy["translation_api_max_chars"] = max(
            80,
            min(
                2000,
                int(
                    self._parse_int_value(
                        policy.get("translation_api_max_chars", 600),
                        default=600,
                    )
                ),
            ),
        )
        policy["apply_custom_dict_first"] = self._coerce_bool(
            policy.get("apply_custom_dict_first", True),
            True,
        )
        policy["glyph_injection_enabled"] = self._coerce_bool(
            policy.get("glyph_injection_enabled", True),
            True,
        )
        policy["id_override_enabled"] = self._coerce_bool(
            policy.get("id_override_enabled", True),
            True,
        )

        return policy

    def _candidate_custom_dictionary_paths(self, raw_path: Any) -> List[Path]:
        """Monta lista de caminhos candidatos para o dicionário customizado."""
        if raw_path is None:
            return []
        txt = str(raw_path).strip()
        if not txt:
            return []
        p = Path(txt)
        project_dir = self._project_root_dir()
        candidates: List[Path] = []
        if p.is_absolute():
            candidates.append(p)
        else:
            candidates.extend(
                [
                    project_dir / txt,
                    project_dir / "interface" / txt,
                    project_dir / "core" / txt,
                ]
            )
        uniq: List[Path] = []
        seen: set = set()
        for cand in candidates:
            try:
                rc = cand.resolve()
            except Exception:
                rc = cand
            if rc in seen:
                continue
            seen.add(rc)
            uniq.append(cand)
        return uniq

    def _load_custom_dictionary_runtime(self) -> None:
        """Carrega dicionário customizado (palavras/frases) para todo o fluxo."""
        self._custom_dictionary = {}
        self._custom_dict_word_map = {}
        self._custom_dict_phrase_items = []
        self._custom_dict_path = None
        raw_path = self._translation_runtime_policy.get("custom_dictionary")
        candidates = self._candidate_custom_dictionary_paths(raw_path)
        selected: Optional[Path] = None
        for cand in candidates:
            if cand.exists():
                selected = cand
                break
        if selected is None:
            return
        try:
            data = json.loads(selected.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(data, dict):
            return
        self._custom_dict_path = str(selected)
        for raw_key, raw_val in data.items():
            key = self._normalize_unicode_nfc(str(raw_key or "")).strip()
            val = self._normalize_unicode_nfc(str(raw_val or "")).strip()
            if not key or not val:
                continue
            self._custom_dictionary[key] = val
            low = key.lower()
            if re.fullmatch(r"[A-Za-zÀ-ÿ0-9']+", key):
                self._custom_dict_word_map[low] = val
                # Integra no glossário-base para uso uniforme.
                self._en_to_pt_words[low] = val
            else:
                self._custom_dict_phrase_items.append((key, val))
        self._custom_dict_phrase_items.sort(key=lambda kv: len(kv[0]), reverse=True)

    def _collect_guardrail_warnings(self) -> List[str]:
        """
        Lista avisos quando guardrails obrigatórios forem desativados via config.
        Mantém o pipeline funcional, mas deixa explícito o risco ao usuário.
        """
        warnings: List[str] = []
        policy = self._translation_runtime_policy if isinstance(self._translation_runtime_policy, dict) else {}
        if not self._coerce_bool(policy.get("normalize_nfc"), True):
            warnings.append(
                "Guardrail desativado: normalize_nfc=false (acentos podem quebrar por decomposição Unicode)."
            )
        if not self._coerce_bool(policy.get("tilemap_require_tbl"), True):
            warnings.append(
                "Guardrail desativado: tilemap_require_tbl=false (tilemap pode receber escrita sem TBL dedicado)."
            )
        if not self._coerce_bool(policy.get("tilemap_fail_fast_without_tbl"), True):
            warnings.append(
                "Guardrail desativado: tilemap_fail_fast_without_tbl=false (pipeline não vai bloquear ausência de TBL)."
            )
        if not self._coerce_bool(policy.get("auto_generate_diff_ranges"), True):
            warnings.append(
                "Guardrail desativado: auto_generate_diff_ranges=false (reinserção dependerá de arquivo externo manual)."
            )
        if not self._coerce_bool(policy.get("auto_relocate_if_needed"), True):
            warnings.append(
                "Guardrail desativado: auto_relocate_if_needed=false (overflows com ponteiro podem ficar bloqueados)."
            )
        if not self._coerce_bool(policy.get("apply_custom_dict_first"), True):
            warnings.append(
                "Guardrail desativado: apply_custom_dict_first=false (dicionário manual perde prioridade máxima)."
            )
        if not self._coerce_bool(policy.get("translation_api_fallback"), True):
            warnings.append(
                "Guardrail desativado: translation_api_fallback=false (sem fallback online para pendências)."
            )
        if not self._coerce_bool(policy.get("glyph_injection_enabled"), True):
            warnings.append(
                "Guardrail desativado: glyph_injection_enabled=false (glifos ausentes podem gerar caracteres inválidos)."
            )
        if policy.get("custom_dictionary") and not self._custom_dictionary:
            warnings.append(
                f"Aviso: dicionário customizado configurado mas não carregado ({policy.get('custom_dictionary')})."
            )
        return warnings

    def _normalize_unicode_nfc(self, text: Any) -> str:
        """Normaliza string em NFC quando a política estiver ativa."""
        raw = text if isinstance(text, str) else str(text or "")
        if not self._coerce_bool(
            self._translation_runtime_policy.get("normalize_nfc"), True
        ):
            return raw
        try:
            return unicodedata.normalize("NFC", raw)
        except Exception:
            return raw

    def _apply_custom_dictionary(self, text: str) -> Tuple[str, int]:
        """Aplica dicionário customizado em frases e palavras, preservando caixa."""
        if not isinstance(text, str) or not text:
            return "", 0
        out = self._normalize_unicode_nfc(text)
        changed = 0

        for src, dst in self._custom_dict_phrase_items:
            pattern = re.compile(re.escape(src), flags=re.IGNORECASE)
            out, replaced = pattern.subn(dst, out)
            changed += int(replaced)

        if self._custom_dict_word_map:
            def _repl(match: re.Match) -> str:
                nonlocal changed
                token = match.group(0)
                mapped = self._custom_dict_word_map.get(token.lower())
                if not mapped:
                    return token
                changed += 1
                if token.isupper():
                    return mapped.upper()
                if token[:1].isupper():
                    return mapped[:1].upper() + mapped[1:]
                return mapped

            out = re.sub(r"[A-Za-zÀ-ÿ0-9']+", _repl, out)
        return out, int(changed)

    def _translate_with_api_preserving_placeholders(self, text: str) -> str:
        """
        Traduz preservando placeholders de controle (ex.: {B:01}).
        Faz a tradução por segmento para evitar perda/corrupção dos tokens.
        """
        if not isinstance(text, str):
            return ""
        src = self._normalize_unicode_nfc(text).strip()
        if not src or "{B:" not in src:
            return ""

        token_re = re.compile(r"(\{B:[0-9A-Fa-f]{2}\})")
        parts = token_re.split(src)
        if len(parts) <= 1:
            return ""

        out_parts: List[str] = []
        changed = False
        for part in parts:
            if part == "":
                continue
            if token_re.fullmatch(part):
                out_parts.append(part)
                continue
            if not part.strip():
                out_parts.append(part)
                continue
            translated = self._translate_with_api_fallback(part, _skip_token_split=True)
            if translated and (
                self._normalize_compare_text(translated) != self._normalize_compare_text(part)
            ):
                out_parts.append(translated)
                changed = True
            else:
                out_parts.append(part)

        if not changed:
            return ""
        return "".join(out_parts).strip()

    def _translate_with_api_fallback(self, text: str, _skip_token_split: bool = False) -> str:
        """
        Fallback de tradução online para casos residuais.
        Atualmente suporta Google endpoint público e LibreTranslate.
        """
        if not self._coerce_bool(
            self._translation_runtime_policy.get("translation_api_fallback"), True
        ):
            return ""
        if requests is None:
            return ""
        src = self._normalize_unicode_nfc(text).strip()
        if not src:
            return ""
        if (not _skip_token_split) and "{B:" in src:
            token_safe = self._translate_with_api_preserving_placeholders(src)
            if token_safe:
                return token_safe
        if len(src) > 220:
            max_chars = int(
                self._parse_int_value(
                    self._translation_runtime_policy.get("translation_api_max_chars", 600),
                    default=600,
                )
            )
            max_chars = max(80, min(max_chars, 2000))
            if len(src) > max_chars:
                return ""
        if not self._looks_phrase_like_text(src):
            return ""

        service = str(
            self._translation_runtime_policy.get("translation_service", "google")
        ).strip().lower()
        source_lang = str(
            self._translation_runtime_policy.get("translation_api_source_lang", "en")
        ).strip() or "en"
        target_lang_raw = str(
            self._translation_runtime_policy.get("translation_api_target_lang", "pt-BR")
        ).strip() or "pt-BR"
        target_lang = "pt" if target_lang_raw.lower().startswith("pt") else target_lang_raw
        timeout_s = int(
            self._parse_int_value(
                self._translation_runtime_policy.get("translation_api_timeout", 8),
                default=8,
            )
        )
        timeout_s = max(3, min(timeout_s, 30))
        cache_key = f"{service}|{source_lang}|{target_lang}|{src}"
        if cache_key in self._api_fallback_cache:
            return self._api_fallback_cache.get(cache_key, "")

        translated = ""
        self._api_fallback_calls += 1
        try:
            if service in {"google", "google_free", "googletranslate", "microsoft", "yandex", "deepl"}:
                resp = requests.get(
                    "https://translate.googleapis.com/translate_a/single",
                    params={
                        "client": "gtx",
                        "sl": source_lang,
                        "tl": target_lang,
                        "dt": "t",
                        "q": src,
                    },
                    timeout=timeout_s,
                )
                if resp.status_code == 200:
                    payload = resp.json()
                    if isinstance(payload, list) and payload and isinstance(payload[0], list):
                        chunks = []
                        for row in payload[0]:
                            if isinstance(row, list) and row:
                                chunks.append(str(row[0] or ""))
                        translated = "".join(chunks).strip()
            elif service in {"libre", "libretranslate"}:
                url = str(
                    self._translation_runtime_policy.get(
                        "translation_api_url", "https://libretranslate.de/translate"
                    )
                ).strip()
                body: Dict[str, Any] = {
                    "q": src,
                    "source": source_lang,
                    "target": target_lang,
                    "format": "text",
                }
                api_key = str(self._translation_runtime_policy.get("translation_api_key", "") or "").strip()
                if api_key:
                    body["api_key"] = api_key
                resp = requests.post(url, json=body, timeout=timeout_s)
                if resp.status_code == 200:
                    payload = resp.json()
                    translated = str(payload.get("translatedText", "") or "").strip()
        except Exception:
            translated = ""

        translated = self._normalize_unicode_nfc(translated).strip()
        if translated and self._normalize_compare_text(translated) != self._normalize_compare_text(src):
            self._api_fallback_success += 1
            self._api_fallback_cache[cache_key] = translated
            return translated
        self._api_fallback_cache[cache_key] = ""
        return ""

    def _detect_platform_from_path(self, rom_path: Any) -> str:
        """Infere plataforma principal pela extensão da ROM."""
        if not rom_path:
            return "SMS"
        try:
            ext = Path(str(rom_path)).suffix.lower()
        except Exception:
            ext = ""
        return str(self.PLATFORM_BY_EXT.get(ext, "SMS"))

    def _apply_platform_overrides(self, platform: str) -> None:
        """Aplica ajustes de glossário/layout para a plataforma alvo."""
        plat = str(platform or "SMS").upper()
        self._target_platform = plat
        self._pt_hint_words = set(self.PT_HINT_WORDS)
        self._en_hint_words = set(self.EN_HINT_WORDS)
        self._en_stopwords_gate = set(self.EN_STOPWORDS_GATE)
        self._en_to_pt_words = dict(self.EN_TO_PT_WORDS)

        extra_hints = set(self.PLATFORM_HINTS_EXTRA.get(plat, set()) or set())
        if extra_hints:
            self._en_hint_words.update(extra_hints)
            self._en_stopwords_gate.update(extra_hints)

        extra_stop = set(self.PLATFORM_STOPWORDS_EXTRA.get(plat, set()) or set())
        if extra_stop:
            self._en_stopwords_gate.update(extra_stop)

        extra_gloss = dict(self.PLATFORM_GLOSSARY_EXTRA.get(plat, {}) or {})
        if extra_gloss:
            self._en_to_pt_words.update(extra_gloss)
        if getattr(self, "_custom_dict_word_map", None):
            self._en_to_pt_words.update(self._custom_dict_word_map)

    def set_target_rom(self, rom_path: Any) -> None:
        """Define plataforma alvo a partir da ROM para heurísticas de tradução."""
        self._apply_platform_overrides(self._detect_platform_from_path(rom_path))

    def _get_dialog_defaults(self) -> Dict[str, int]:
        defaults = self.PLATFORM_DIALOG_DEFAULTS.get(self._target_platform, {})
        return {
            "width": int(defaults.get("width", 28)),
            "lines": int(defaults.get("lines", 4)),
            "max_lines_hard": int(defaults.get("max_lines_hard", 8)),
        }

    def _load_game_engineering_profile(self, rom_crc32: str) -> Dict[str, Any]:
        """Carrega perfil de engenharia por CRC e retorna resumo."""
        self._game_engineering_profile = {}
        self._game_engineering_profile_summary = {
            "rom_crc32": str(rom_crc32 or "").upper(),
            "enabled": bool(self._game_engineering_manager is not None),
            "has_crc_profile": False,
            "profile_id": None,
            "profile_name": None,
            "profile_version": None,
            "profile_file": None,
            "compression": {},
        }
        if not self._game_engineering_manager:
            return dict(self._game_engineering_profile_summary)

        try:
            profile = self._game_engineering_manager.get_profile(rom_crc32)
            summary = self._game_engineering_manager.profile_summary(profile)
            self._game_engineering_profile = profile if isinstance(profile, dict) else {}
            self._game_engineering_profile_summary.update(
                {
                    "has_crc_profile": bool(summary.get("has_crc_profile", False)),
                    "profile_id": summary.get("profile_id"),
                    "profile_name": summary.get("profile_name"),
                    "profile_version": summary.get("profile_version"),
                    "profile_file": summary.get("profile_file"),
                    "compression": self._game_engineering_manager.get_compression_policy(
                        self._game_engineering_profile
                    ),
                }
            )
        except Exception:
            self._game_engineering_profile = {}
        return dict(self._game_engineering_profile_summary)

    def _apply_game_engineering_text(self, text: str, stage: str = "reinsert") -> Tuple[str, int]:
        """Aplica pipeline de script/charset do perfil de engenharia."""
        if not isinstance(text, str):
            return "", 0
        if not self._game_engineering_manager or not self._game_engineering_profile:
            return text, 0
        try:
            # Respeita a política de charset do profile (strip_accents, allowed regex etc).
            # Não força diacríticos automaticamente por TBL para evitar injeção de bytes
            # de controle em ROMs com mapeamentos não confiáveis.
            return self._game_engineering_manager.apply_text_pipeline(
                text, self._game_engineering_profile, stage=stage
            )
        except Exception:
            return text, 0

    # ---------- mapping ----------

    def _guess_mapping_path(self, translated_path: Path, rom_path: Optional[Path] = None) -> Optional[Path]:
        # 1) mesmo diretório
        candidates = list(translated_path.parent.glob("*_mapping.json"))
        if candidates:
            # tenta casar pelo prefixo
            base = translated_path.stem
            for suf in ["_translated", "_TRANSLATED", "_clean_blocks", "_CLEAN_EXTRACTED", "_clean", "_CLEAN"]:
                base = base.replace(suf, "")
            for c in candidates:
                if c.stem.startswith(base):
                    return c
            return candidates[0]

        # 1.1) pasta _interno (quando auxiliares ficam ocultos)
        interno = translated_path.parent / "_interno"
        if interno.exists():
            candidates = list(interno.glob("*_mapping.json"))
            if candidates:
                base = translated_path.stem
                for suf in ["_translated", "_TRANSLATED", "_clean_blocks", "_CLEAN_EXTRACTED", "_clean", "_CLEAN"]:
                    base = base.replace(suf, "")
                for c in candidates:
                    if c.stem.startswith(base):
                        return c
                return candidates[0]

        # 1.2) pasta irmã 1_extracao (estrutura: CRC32/2_traducao → CRC32/1_extracao)
        extracao_dir = translated_path.parent.parent / "1_extracao"
        if extracao_dir.exists():
            candidates = list(extracao_dir.glob("*_mapping.json"))
            if candidates:
                base = translated_path.stem
                for suf in ["_translated", "_TRANSLATED", "_clean_blocks", "_CLEAN_EXTRACTED", "_clean", "_CLEAN",
                             "_pure_text", "_optimized"]:
                    base = base.replace(suf, "")
                for c in candidates:
                    if c.stem.startswith(base):
                        return c
                return candidates[0]

        # 2) pasta da ROM original (se fornecida)
        if rom_path is not None:
            cand2 = list(rom_path.parent.glob("*_mapping.json"))
            if cand2:
                return cand2[0]
        return None

    def load_mapping(self, mapping_path: Path):
        data = json.loads(mapping_path.read_text(encoding="utf-8"))
        # Preserva override manual de TBL (ex.: tabela PT-BR carregada pela GUI)
        # para evitar perda do charset custom ao trocar/carregar mapping.
        manual_tbl_loader = None
        manual_tile_entry_len = self._tile_entry_len
        manual_tile_space_seq = self._tile_space_seq
        if getattr(self._tbl_loader, "_neurorom_manual_override", False):
            manual_tbl_loader = self._tbl_loader
        # suporta formato lista (legacy)
        if isinstance(data, list):
            self.mapping_crc32 = None
            entries = data
        else:
            self.mapping_crc32 = str(data.get("file_crc32", data.get("crc32", ""))).upper() or None
            entries = data.get("entries") or data.get("text_blocks") or data
        # Reseta cache de TBL quando muda mapping
        self._tbl_loader = None
        self._tile_entry_len = 1
        self._tile_space_seq = None
        mp: Dict[str, MapEntry] = {}

        # Se for lista (novo formato V1), converte para iteração
        if isinstance(entries, list):
            items = [(str(v.get("id", i)), v) for i, v in enumerate(entries)]
        else:
            items = entries.items()

        for k, v in items:
            # pointer_refs detalhados (quando presentes)
            ptr_refs: List[Dict[str, Any]] = []
            raw_ptr_refs = v.get("pointer_refs", []) or v.get("pointer_sources", []) or []
            for ref in raw_ptr_refs:
                poff = self._parse_int_value(ref.get("ptr_offset"), default=-1)
                if poff < 0:
                    continue
                ptr_refs.append(
                    {
                        "ptr_offset": int(poff),
                        "ptr_size": self._parse_int_value(ref.get("ptr_size", 2), default=2),
                        "endianness": str(ref.get("endianness", "little")).lower(),
                        "addressing_mode": str(ref.get("addressing_mode", "ABSOLUTE")),
                        "bank_addend": self._parse_int_value(ref.get("bank_addend", 0), default=0),
                    }
                )

            # pointer_offsets simples (compat)
            pointer_offsets = [int(x) for x in v.get("pointer_offsets", [])]
            if not pointer_offsets:
                ptr_entry_off = v.get("pointer_entry_offset")
                if ptr_entry_off is not None:
                    try:
                        pointer_offsets = [int(ptr_entry_off)]
                    except (TypeError, ValueError):
                        pointer_offsets = []
            term_val = self._parse_optional_int_value(v.get("terminator"))
            if term_val is not None:
                term_val = int(term_val) & 0xFF
            raw_len_val = self._parse_optional_int_value(
                v.get("raw_len", v.get("max_len_bytes", v.get("max_length")))
            )
            if raw_len_val is not None and int(raw_len_val) <= 0:
                raw_len_val = None
            mp[k] = MapEntry(
                key=k,
                offset=int(v["offset"]),
                max_len=int(v.get("max_len", v.get("max_bytes", v.get("max_length", 0)))),
                raw_len=(int(raw_len_val) if raw_len_val is not None else None),
                category=str(v.get("category", "Unknown")),
                has_pointer=bool(v.get("has_pointer", False)),
                pointer_offsets=pointer_offsets,
                pointer_refs=ptr_refs,
                terminator=(int(term_val) if term_val is not None else None),
                encoding=str(v.get("encoding", "ascii")),
                reinsertion_safe=bool(v.get("reinsertion_safe", True)),
                blocked_reason=v.get("blocked_reason"),
            )
            # Se só temos pointer_offsets, cria refs básicas
            if mp[k].pointer_offsets and not mp[k].pointer_refs:
                mp[k].pointer_refs = [
                    {
                        "ptr_offset": int(poff),
                        "ptr_size": 2,
                        "endianness": "little",
                        "addressing_mode": "ABSOLUTE",
                        "bank_addend": 0,
                    }
                    for poff in mp[k].pointer_offsets
                ]
            mp[k].has_pointer = bool(
                mp[k].pointer_refs or mp[k].pointer_offsets or v.get("has_pointer", False)
            )
        self.mapping = mp
        if manual_tbl_loader is not None:
            self._tbl_loader = manual_tbl_loader
            try:
                self._tile_entry_len = max(
                    1,
                    int(getattr(manual_tbl_loader, "max_entry_len", manual_tile_entry_len or 1)),
                )
            except Exception:
                self._tile_entry_len = max(1, int(manual_tile_entry_len or 1))
            try:
                reverse_map = getattr(manual_tbl_loader, "reverse_map", {}) or {}
                self._tile_space_seq = reverse_map.get(" ")
            except Exception:
                self._tile_space_seq = manual_tile_space_seq

    def _validate_entry(self, entry: MapEntry, rom_size: int) -> List[str]:
        """Valida limites e parâmetros do mapeamento antes de escrever."""
        errors: List[str] = []
        payload_len = self._parse_optional_int_value(entry.max_len)
        if payload_len is None or int(payload_len) <= 0:
            payload_len = self._parse_optional_int_value(entry.raw_len)
        if payload_len is None:
            payload_len = 0
        payload_len = int(payload_len)
        total_len = payload_len + (1 if entry.terminator is not None else 0)

        if entry.offset < 0 or entry.offset >= rom_size:
            errors.append("offset fora do tamanho da ROM")

        if payload_len <= 0:
            errors.append("max_len inválido (<= 0)")

        if entry.offset + total_len > rom_size:
            errors.append("offset + tamanho do slot excede tamanho da ROM")

        if entry.terminator is not None and not (0 <= entry.terminator <= 255):
            errors.append("terminator fora de 0-255")

        for poff in entry.pointer_offsets:
            if poff < 0 or poff + 1 >= rom_size:
                errors.append("pointer_offset fora do tamanho da ROM")
                break

        return errors

    def _parse_int_value(self, value: Any, default: int = 0) -> int:
        """Converte strings numéricas (hex/dec, com sinal) para int."""
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return default
            s_low = s.lower()
            # casos vindos do extractor: "0x-8000"
            if s_low.startswith("0x-"):
                s_low = "-0x" + s_low[3:]
            try:
                if s_low.startswith(("-0x", "+0x")):
                    sign = -1 if s_low.startswith("-") else 1
                    return sign * int(s_low[3:], 16)
                if s_low.startswith("0x"):
                    return int(s_low, 16)
                return int(s_low, 10)
            except ValueError:
                return default
        return default

    def _parse_optional_int_value(self, value: Any) -> Optional[int]:
        """Converte valor numérico para int opcional."""
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        parsed = self._parse_int_value(value, default=-(1 << 60))
        if parsed == -(1 << 60):
            return None
        return int(parsed)

    def _resolve_compression_algorithm(self, value: Any):
        """Resolve string/enum para CompressionAlgorithm."""
        if CompressionAlgorithm is None:
            return None
        if isinstance(value, CompressionAlgorithm):
            return value
        raw = self._normalize_compression_name(value)
        if not raw:
            return None
        aliases = {
            "RLE": "RLE",
            "LZSS": "LZSS",
            "LZ77": "LZ77",
            "LZ10": "LZ10",
            "LZ11": "LZ11",
            "YAY0": "YAY0",
            "YAZ0": "YAZ0",
        }
        key = aliases.get(raw, raw)
        return getattr(CompressionAlgorithm, key, None)

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

    def _platform_allows_compression_algorithm(self, value: Any) -> bool:
        algo = self._normalize_compression_name(value)
        if not algo:
            return False
        plat = str(self._target_platform or "SMS").upper()
        allowed = self.COMPRESSION_PROFILE_BY_PLATFORM.get(plat, [])
        if not allowed:
            return True
        return str(algo).upper() in {str(x).upper() for x in allowed}

    def _detect_compressed_regions_for_rom(self, rom_bytes: bytes) -> List[Dict[str, Any]]:
        if not rom_bytes or CompressionDetector is None:
            return []
        try:
            detector = CompressionDetector(bytes(rom_bytes))
            regions = detector.detect(block_size=2048)
        except Exception as exc:
            if DEBUG:
                print(f"[WARN] CompressionDetector indisponível: {exc}")
            return []

        normalized: List[Dict[str, Any]] = []
        for reg in regions or []:
            try:
                off = int(getattr(reg, "offset", -1))
                size = int(getattr(reg, "size", 0))
            except Exception:
                continue
            if off < 0 or size <= 0:
                continue
            normalized.append(
                {
                    "offset": int(off),
                    "size": int(size),
                    "algorithm": self._normalize_compression_name(getattr(reg, "algorithm", "")),
                    "confidence": float(getattr(reg, "confidence", 0.0) or 0.0),
                }
            )
        return normalized

    def _infer_algorithm_from_regions(self, c_off: int, c_size: int) -> str:
        if c_off < 0 or c_size <= 0:
            return ""
        best_algo = ""
        best_overlap = 0
        end = c_off + c_size
        for reg in self._detected_compressed_regions or []:
            r_off = int(reg.get("offset", -1))
            r_size = int(reg.get("size", 0))
            if r_off < 0 or r_size <= 0:
                continue
            r_end = r_off + r_size
            overlap = max(0, min(end, r_end) - max(c_off, r_off))
            if overlap > best_overlap:
                best_overlap = overlap
                best_algo = self._normalize_compression_name(reg.get("algorithm", ""))
        return str(best_algo or "")

    def _is_compressed_meta_entry(self, meta: Optional[Dict[str, Any]]) -> bool:
        """Detecta se entrada JSONL pertence a bloco comprimido reinserível."""
        if not isinstance(meta, dict):
            return False
        source = str(meta.get("source", "") or "").upper()
        if "COMPRESSED_BLOCK_AUTO" in source:
            return True
        if (
            meta.get("compressed_offset") is not None
            and (
                meta.get("compression_algorithm") is not None
                or meta.get("algorithm") is not None
                or meta.get("compression") is not None
                or meta.get("compressed_size") is not None
            )
        ):
            return True
        return False

    def _collect_compressed_translation_blocks(
        self,
        translated: Dict[str, str],
        fallback_entries: Optional[Dict[str, Dict[str, Any]]],
    ) -> Dict[str, Dict[str, Any]]:
        """Agrupa traduções por bloco comprimido (offset + algoritmo)."""
        blocks: Dict[str, Dict[str, Any]] = {}
        if not translated or not isinstance(fallback_entries, dict):
            return blocks

        for key, text in translated.items():
            meta = fallback_entries.get(key)
            if not self._is_compressed_meta_entry(meta):
                continue
            c_off = self._parse_optional_int_value(
                meta.get("compressed_offset", meta.get("rom_offset"))
            )
            c_size = self._parse_optional_int_value(
                meta.get("compressed_size", meta.get("block_size"))
            )
            local_off = self._parse_optional_int_value(
                meta.get("local_offset", meta.get("decompressed_local_offset"))
            )
            max_len = self._parse_optional_int_value(
                meta.get("max_len_bytes", meta.get("max_len", meta.get("max_length")))
            )
            alg_raw = meta.get("compression_algorithm", meta.get("algorithm", meta.get("compression")))
            term = self._parse_optional_int_value(meta.get("terminator"))
            if c_off is None or c_size is None or local_off is None or max_len is None:
                continue
            if c_off < 0 or c_size <= 0 or local_off < 0 or max_len <= 0:
                continue
            alg_name = self._normalize_compression_name(alg_raw)
            if not alg_name:
                alg_name = self._infer_algorithm_from_regions(int(c_off), int(c_size))
            if not alg_name:
                continue
            alg_enum = self._resolve_compression_algorithm(alg_name)
            sig = f"{int(c_off)}|{int(c_size)}|{alg_name}"
            if sig not in blocks:
                blocks[sig] = {
                    "compressed_offset": int(c_off),
                    "compressed_size": int(c_size),
                    "algorithm_name": str(alg_name),
                    "algorithm": alg_enum,
                    "entries": [],
                }
            orig_text = self._extract_source_text(meta)
            blocks[sig]["entries"].append(
                {
                    "key": str(key),
                    "text": str(text or ""),
                    "local_offset": int(local_off),
                    "max_len_bytes": int(max_len),
                    "terminator": int(term) if term is not None else None,
                    "orig_text": orig_text,
                }
            )

        for block in blocks.values():
            block["entries"].sort(
                key=lambda it: (
                    int(it.get("local_offset", 0)),
                    int(it.get("max_len_bytes", 0)),
                    str(it.get("key", "")),
                )
            )
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

    def _resolve_entry_payload_len(
        self,
        entry: MapEntry,
        meta: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Resolve tamanho efetivo do payload de texto (sem terminador).

        Prioriza metadados de extração (`raw_len`/`max_len_bytes`) para evitar
        escrita além do bloco real quando há aliases/sobreposição.
        """
        candidates: List[int] = []
        if isinstance(meta, dict):
            for key in ("raw_len", "max_len_bytes", "max_length", "max_len", "max_bytes"):
                parsed = self._parse_optional_int_value(meta.get(key))
                if parsed is not None and int(parsed) > 0:
                    candidates.append(int(parsed))

        entry_raw = self._parse_optional_int_value(getattr(entry, "raw_len", None))
        if entry_raw is not None and int(entry_raw) > 0:
            candidates.append(int(entry_raw))

        entry_max = self._parse_optional_int_value(getattr(entry, "max_len", None))
        if entry_max is not None and int(entry_max) > 0:
            candidates.append(int(entry_max))

        for val in candidates:
            if int(val) > 0:
                return int(val)
        return 1

    def _resolve_entry_slot_total_len(
        self,
        entry: MapEntry,
        meta: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Retorna tamanho total do slot (payload + terminador, quando existir)."""
        payload_len = int(self._resolve_entry_payload_len(entry, meta))
        term_extra = 1 if entry.terminator is not None else 0
        return max(1, payload_len + term_extra)

    def _build_pointer_protected_ranges(
        self,
        fallback_entries: Optional[Dict[str, Dict[str, Any]]],
    ) -> List[Tuple[int, int, str]]:
        """
        Constrói faixas de texto que não podem receber escrita de ponteiro.

        Evita corrupção do tipo "pointer overwrite" em bytes de strings exibíveis.
        """
        ranges: List[Tuple[int, int, str]] = []
        fallback = fallback_entries if isinstance(fallback_entries, dict) else {}
        for key, entry in self.mapping.items():
            if not isinstance(entry, MapEntry):
                continue
            meta = fallback.get(str(key))
            if self._is_non_plausible_text_meta(meta):
                continue
            raw_len = int(self._resolve_entry_payload_len(entry, meta if isinstance(meta, dict) else None))
            start = int(entry.offset)
            end = start + int(raw_len) + (1 if entry.terminator is not None else 0)
            if start < 0 or end <= start:
                continue
            ranges.append((start, end, str(key)))
        ranges.sort(key=lambda it: (int(it[0]), int(it[1]), str(it[2])))
        return ranges

    def _pointer_ref_overlaps_protected_text(
        self,
        ptr_offset: Optional[int],
        ptr_size: Optional[int],
        protected_ranges: List[Tuple[int, int, str]],
    ) -> bool:
        """Retorna True se ptr_offset/ptr_size colidir com faixa de texto protegida."""
        if ptr_offset is None:
            return True
        off = int(ptr_offset)
        size = int(ptr_size) if ptr_size is not None else 2
        if size <= 0:
            size = 2
        if off < 0:
            return True
        end = off + size
        for start, stop, _owner in protected_ranges:
            if start >= end:
                break
            if off < stop and end > start:
                return True
        return False

    def _filter_pointer_refs_for_safety(
        self,
        refs: List[Dict[str, Any]],
        protected_ranges: List[Tuple[int, int, str]],
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Remove pointer refs que colidem com texto.

        Retorna (refs_filtrados, quantidade_rejeitada).
        """
        safe_refs: List[Dict[str, Any]] = []
        rejected = 0
        for ref in refs or []:
            poff = self._parse_optional_int_value(ref.get("ptr_offset"))
            psize = self._parse_optional_int_value(ref.get("ptr_size"))
            if self._pointer_ref_overlaps_protected_text(poff, psize, protected_ranges):
                rejected += 1
                continue
            safe_refs.append(ref)
        return safe_refs, int(rejected)

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

    def _apply_compressed_block_translations(
        self,
        rom: bytearray,
        translated: Dict[str, str],
        fallback_entries: Optional[Dict[str, Dict[str, Any]]],
        stats: Dict[str, int],
        items_report: List[Dict[str, Any]],
        not_applied: List[Dict[str, Any]],
        charset_stats: Dict[str, int],
    ) -> Dict[str, Any]:
        """
        Aplica traduções em blocos comprimidos:
        decompress -> patch -> recompress -> roundtrip validate.
        """
        self._detected_compressed_regions = self._detect_compressed_regions_for_rom(bytes(rom))
        summary = {
            "enabled": bool(MultiDecompress and MultiCompress and CompressionAlgorithm),
            "candidates": 0,
            "blocks_total": 0,
            "blocks_applied": 0,
            "blocks_relocated": 0,
            "pointer_updates": 0,
            "inserted_items": 0,
            "truncated_items": 0,
            "blocked_items": 0,
            "roundtrip_baseline_fail_blocks": 0,
            "roundtrip_fail_blocks": 0,
            "unsupported_algorithm_blocks": 0,
            "examples": {
                "applied": [],
                "blocked": [],
            },
            "limitations": [],
        }
        compact_glossary_crc32 = (
            str(self.mapping_crc32 or self._jsonl_declared_crc32 or "")
            .strip()
            .upper()
            or None
        )
        strip_accents_before_fit = self._should_strip_accents_for_crc(compact_glossary_crc32)

        blocks = self._collect_compressed_translation_blocks(translated, fallback_entries)
        summary["blocks_total"] = int(len(blocks))
        summary["candidates"] = int(
            sum(len(block.get("entries", [])) for block in blocks.values())
        )
        if not blocks:
            return summary

        if not summary["enabled"]:
            summary["limitations"].append("Compressão/recompressão indisponível no runtime.")
            for block in blocks.values():
                for it in block.get("entries", []) or []:
                    key = str(it.get("key", ""))
                    summary["blocked_items"] += 1
                    stats["BLOCKED"] += 1
                    not_applied.append(
                        {
                            "key": key,
                            "reason": "compressed_runtime_unavailable",
                        }
                    )
                    items_report.append(
                        {
                            "key": key,
                            "action": "NOT_APPLIED",
                            "reason": "compressed_runtime_unavailable",
                        }
                    )
                    if len(summary["examples"]["blocked"]) < 8:
                        summary["examples"]["blocked"].append(
                            {
                                "key": key,
                                "reason": "compressed_runtime_unavailable",
                            }
                        )
            return summary

        decomp_engine = MultiDecompress()
        comp_engine = MultiCompress()

        for block_sig, block in blocks.items():
            block_off = int(block.get("compressed_offset", 0))
            block_size = int(block.get("compressed_size", 0))
            alg_name = self._normalize_compression_name(
                block.get("algorithm_name", block.get("algorithm"))
            )
            alg = block.get("algorithm")
            entries = block.get("entries", []) or []
            if not entries:
                continue

            if block_off < 0 or block_size <= 0 or block_off + block_size > len(rom):
                for it in entries:
                    summary["blocked_items"] += 1
                    stats["BLOCKED"] += 1
                    not_applied.append({"key": it.get("key"), "reason": "compressed_block_out_of_range"})
                    items_report.append(
                        {
                            "key": it.get("key"),
                            "action": "NOT_APPLIED",
                            "reason": "compressed_block_out_of_range",
                        }
                    )
                continue

            if not self._platform_allows_compression_algorithm(alg_name):
                summary["unsupported_algorithm_blocks"] += 1
                for it in entries:
                    summary["blocked_items"] += 1
                    stats["BLOCKED"] += 1
                    not_applied.append({"key": it.get("key"), "reason": "compressed_algorithm_not_allowed_for_platform"})
                    items_report.append(
                        {
                            "key": it.get("key"),
                            "action": "NOT_APPLIED",
                            "reason": "compressed_algorithm_not_allowed_for_platform",
                        }
                    )
                continue

            if alg is None:
                summary["unsupported_algorithm_blocks"] += 1
                for it in entries:
                    summary["blocked_items"] += 1
                    stats["BLOCKED"] += 1
                    not_applied.append({"key": it.get("key"), "reason": "compressed_algorithm_unknown"})
                    items_report.append(
                        {"key": it.get("key"), "action": "NOT_APPLIED", "reason": "compressed_algorithm_unknown"}
                    )
                continue

            orig_comp = bytes(rom[block_off:block_off + block_size])
            dec_res = decomp_engine.decompress(orig_comp, alg)
            if not dec_res.success or not dec_res.data:
                for it in entries:
                    summary["blocked_items"] += 1
                    stats["BLOCKED"] += 1
                    not_applied.append({"key": it.get("key"), "reason": "compressed_decompress_failed"})
                    items_report.append(
                        {"key": it.get("key"), "action": "NOT_APPLIED", "reason": "compressed_decompress_failed"}
                    )
                continue

            baseline_comp = comp_engine.compress(bytes(dec_res.data), alg)
            if (not baseline_comp.success) or (bytes(baseline_comp.data) != orig_comp):
                summary["roundtrip_baseline_fail_blocks"] += 1
                summary["roundtrip_fail_blocks"] += 1
                for it in entries:
                    summary["blocked_items"] += 1
                    stats["BLOCKED"] += 1
                    not_applied.append({"key": it.get("key"), "reason": "compressed_roundtrip_baseline_mismatch"})
                    items_report.append(
                        {
                            "key": it.get("key"),
                            "action": "NOT_APPLIED",
                            "reason": "compressed_roundtrip_baseline_mismatch",
                        }
                    )
                continue

            decomp_buf = bytearray(dec_res.data)
            touched_keys: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []

            for it in entries:
                key = str(it.get("key", ""))
                local_off = int(it.get("local_offset", 0))
                slot_len = int(it.get("max_len_bytes", 0))
                term_val = it.get("terminator")
                term = b""
                if term_val is not None:
                    term = bytes([int(term_val) & 0xFF])
                if slot_len <= 0:
                    summary["blocked_items"] += 1
                    stats["BLOCKED"] += 1
                    not_applied.append({"key": key, "reason": "compressed_slot_invalid"})
                    items_report.append(
                        {"key": key, "action": "NOT_APPLIED", "reason": "compressed_slot_invalid"}
                    )
                    continue
                if local_off < 0 or local_off + slot_len > len(decomp_buf):
                    summary["blocked_items"] += 1
                    stats["BLOCKED"] += 1
                    not_applied.append({"key": key, "reason": "compressed_local_offset_invalid"})
                    items_report.append(
                        {"key": key, "action": "NOT_APPLIED", "reason": "compressed_local_offset_invalid"}
                    )
                    continue

                raw_text = str(it.get("text", "") or "")
                raw_text = apply_compact_glossary(raw_text, compact_glossary_crc32)
                if strip_accents_before_fit:
                    raw_text = strip_accents_for_rom(raw_text)
                it["text"] = raw_text
                src_text = str(it.get("orig_text", "") or "")
                payload_limit = max(0, slot_len - len(term))
                encoded_payload, fallback_cnt, sanitized = self._encode_ascii_with_byte_placeholders(
                    raw_text,
                    preserve_newlines=False,
                )
                encoded = encoded_payload + term

                truncated = False
                reformulated = False
                wrapped = False
                strategy = "CMP_DIRECT"
                if len(encoded) > slot_len:
                    fit = self._fit_ascii_reformulation(
                        text=raw_text,
                        orig_text=src_text,
                        payload_limit=payload_limit,
                        term=term,
                        tokens=self._extract_tokens(src_text),
                        allow_compact=True,
                        allow_hard_trim=True,
                    )
                    if not fit:
                        summary["blocked_items"] += 1
                        stats["BLOCKED"] += 1
                        not_applied.append({"key": key, "reason": "compressed_layout_overflow"})
                        items_report.append(
                            {"key": key, "action": "NOT_APPLIED", "reason": "compressed_layout_overflow"}
                        )
                        continue
                    encoded = fit["encoded_with_term"]
                    truncated = bool(fit.get("hard_trim"))
                    reformulated = bool(fit.get("reformulated"))
                    wrapped = str(fit.get("strategy", "")).startswith("WRAP")
                    strategy = str(fit.get("strategy", "CMP_REFORM"))
                    fallback_cnt = int(fit.get("fallback_chars", fallback_cnt))

                # write segment in decompressed buffer
                decomp_buf[local_off:local_off + slot_len] = b"\x00" * slot_len
                decomp_buf[local_off:local_off + len(encoded)] = encoded
                charset_stats["ascii_items"] += 1
                charset_stats["ascii_fallback_chars"] += int(fallback_cnt)
                touched_keys.append(
                    (
                        it,
                        {
                            "sanitized": sanitized,
                            "encoded_len": len(encoded),
                            "truncated": truncated,
                            "reformulated": reformulated,
                            "wrapped": wrapped,
                            "strategy": strategy,
                        },
                    )
                )

            if not touched_keys:
                continue

            comp_res = comp_engine.compress(bytes(decomp_buf), alg)
            if not comp_res.success or not comp_res.data:
                for it, _meta in touched_keys:
                    key = str(it.get("key", ""))
                    summary["blocked_items"] += 1
                    stats["BLOCKED"] += 1
                    not_applied.append({"key": key, "reason": "compressed_recompress_failed"})
                    items_report.append(
                        {"key": key, "action": "NOT_APPLIED", "reason": "compressed_recompress_failed"}
                    )
                continue

            # round-trip validation (obrigatório)
            rt_res = decomp_engine.decompress(comp_res.data, alg)
            if (not rt_res.success) or (bytes(rt_res.data) != bytes(decomp_buf)):
                summary["roundtrip_fail_blocks"] += 1
                for it, _meta in touched_keys:
                    key = str(it.get("key", ""))
                    summary["blocked_items"] += 1
                    stats["BLOCKED"] += 1
                    not_applied.append({"key": key, "reason": "compressed_roundtrip_fail"})
                    items_report.append(
                        {"key": key, "action": "NOT_APPLIED", "reason": "compressed_roundtrip_fail"}
                    )
                continue

            write_offset = int(block_off)
            relocated = False
            ptr_updates: List[int] = []
            new_comp = bytes(comp_res.data)

            if len(new_comp) <= block_size:
                rom[write_offset:write_offset + block_size] = new_comp + (b"\xFF" * (block_size - len(new_comp)))
            else:
                allow_expand = os.environ.get("NEUROROM_ALLOW_ROM_EXPAND", "1") == "1"
                if not allow_expand:
                    for it, _meta in touched_keys:
                        key = str(it.get("key", ""))
                        summary["blocked_items"] += 1
                        stats["BLOCKED"] += 1
                        not_applied.append({"key": key, "reason": "compressed_no_space_expand_disabled"})
                        items_report.append(
                            {"key": key, "action": "NOT_APPLIED", "reason": "compressed_no_space_expand_disabled"}
                        )
                    continue

                old_len = len(rom)
                new_off = self._align(old_len, 2)
                if new_off > old_len:
                    rom.extend(b"\xFF" * (new_off - old_len))
                rom.extend(new_comp)

                refs = self._find_pointer_refs_for_target(
                    rom_bytes=bytes(rom[:old_len]),
                    old_offset=block_off,
                    new_offset=new_off,
                    max_refs=512,
                )
                if not refs:
                    # rollback
                    del rom[old_len:]
                    for it, _meta in touched_keys:
                        key = str(it.get("key", ""))
                        summary["blocked_items"] += 1
                        stats["BLOCKED"] += 1
                        not_applied.append({"key": key, "reason": "compressed_reloc_no_pointers"})
                        items_report.append(
                            {"key": key, "action": "NOT_APPLIED", "reason": "compressed_reloc_no_pointers"}
                        )
                    continue

                ok_ptr = True
                for ref in refs:
                    value = self._calc_pointer_value(new_off, ref)
                    if value is None or not self._write_pointer_value(rom, ref, value):
                        ok_ptr = False
                        break
                    ptr_updates.append(int(ref.get("ptr_offset", -1)))
                if not ok_ptr:
                    del rom[old_len:]
                    for it, _meta in touched_keys:
                        key = str(it.get("key", ""))
                        summary["blocked_items"] += 1
                        stats["BLOCKED"] += 1
                        not_applied.append({"key": key, "reason": "compressed_reloc_pointer_fail"})
                        items_report.append(
                            {"key": key, "action": "NOT_APPLIED", "reason": "compressed_reloc_pointer_fail"}
                        )
                    continue

                # marca bloco antigo como livre
                rom[block_off:block_off + block_size] = b"\xFF" * block_size
                write_offset = int(new_off)
                relocated = True

            summary["blocks_applied"] += 1
            if relocated:
                summary["blocks_relocated"] += 1
                summary["pointer_updates"] += int(len(ptr_updates))

            for it, meta in touched_keys:
                key = str(it.get("key", ""))
                action = "CMP_REPOINT" if relocated else "CMP_OK"
                final_text = meta.get("sanitized", "")
                if bool(meta.get("wrapped")):
                    stats["WRAP"] += 1
                    action = "CMP_WRAP" if not relocated else "CMP_REPOINT_WRAP"
                if bool(meta.get("reformulated")):
                    stats["REFORM"] += 1
                    if action.endswith("OK"):
                        action = "CMP_REFORM"
                if bool(meta.get("truncated")):
                    stats["TRUNC"] += 1
                    stats["TRUNC_OVERFLOW"] += 1
                    summary["truncated_items"] += 1
                    action = "CMP_SHORT" if not relocated else "CMP_REPOINT_SHORT"
                stats["OK"] += 1
                summary["inserted_items"] += 1
                if isinstance(final_text, str) and final_text.strip():
                    translated[key] = final_text
                items_report.append(
                    {
                        "key": key,
                        "action": action,
                        "reason": "compressed_block_patch",
                        "compressed_offset": f"0x{block_off:06X}",
                        "compressed_size": int(block_size),
                        "new_compressed_size": int(len(new_comp)),
                        "compressed_write_offset": f"0x{write_offset:06X}",
                        "compression_algorithm": str(alg_name or getattr(alg, "value", alg)),
                        "local_offset": int(it.get("local_offset", 0)),
                        "max_len_bytes": int(it.get("max_len_bytes", 0)),
                        "pointer_updates": ptr_updates[:32],
                        "relocated": bool(relocated),
                    }
                )
                if len(summary["examples"]["applied"]) < 8:
                    summary["examples"]["applied"].append(
                        {
                            "key": key,
                            "action": action,
                            "compressed_offset": f"0x{block_off:06X}",
                            "compression_algorithm": str(alg_name or getattr(alg, "value", alg)),
                            "relocated": bool(relocated),
                        }
                    )

        if not summary["examples"]["blocked"]:
            for item in items_report:
                reason = str(item.get("reason", ""))
                if not reason.startswith("compressed_"):
                    continue
                summary["examples"]["blocked"].append(
                    {
                        "key": str(item.get("key", "")),
                        "reason": reason,
                    }
                )
                if len(summary["examples"]["blocked"]) >= 8:
                    break

        return summary

    def _is_jsonl_meta_record(self, obj: Dict[str, Any]) -> bool:
        """Detecta registro de metadados no JSONL."""
        if not isinstance(obj, dict):
            return False
        record_type = str(obj.get("type", obj.get("record_type", ""))).lower()
        if record_type == "meta":
            return True
        if bool(obj.get("meta")):
            return True
        has_identity = ("rom_crc32" in obj) or ("rom_size" in obj)
        has_text_fields = any(
            key in obj for key in ("text_src", "text_dst", "translated", "translation", "translated_text")
        )
        if has_identity and not has_text_fields:
            return True
        return False

    def _extract_jsonl_identity(self, path: Path) -> Dict[str, Any]:
        """Extrai rom_crc32/rom_size declarados em JSONL de tradução."""
        declared_crc32: Optional[str] = None
        declared_size: Optional[int] = None
        if not path.exists():
            return {"rom_crc32": None, "rom_size": None}

        for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue

            if obj.get("rom_crc32") is not None and declared_crc32 is None:
                declared_crc32 = str(obj.get("rom_crc32")).upper().strip()
            if obj.get("rom_size") is not None and declared_size is None:
                declared_size = self._parse_optional_int_value(obj.get("rom_size"))

            if self._is_jsonl_meta_record(obj) and declared_crc32 and declared_size is not None:
                break

        return {"rom_crc32": declared_crc32, "rom_size": declared_size}

    def _candidate_strict_ptbr_override_paths(
        self, translated_path: Path, rom_crc32: str
    ) -> List[Path]:
        """Lista caminhos candidatos para overrides PT-BR estritos."""
        crc = str(rom_crc32 or "").upper()
        if not crc:
            return []
        names = [
            f"strict_ptbr_overrides_{crc}.json",
            f"{crc}_strict_ptbr_overrides.json",
            f"{crc}_ptbr_overrides.json",
        ]
        parents = [translated_path.parent]
        if translated_path.parent.parent.exists():
            parents.append(translated_path.parent.parent)
            two_trad = translated_path.parent.parent / "2_traducao"
            if two_trad.exists():
                parents.append(two_trad)

        out: List[Path] = []
        seen: set = set()
        for parent in parents:
            for name in names:
                cand = parent / name
                try:
                    rc = cand.resolve()
                except Exception:
                    rc = cand
                if rc in seen:
                    continue
                seen.add(rc)
                out.append(cand)
        return out

    def _load_strict_ptbr_overrides(
        self, translated_path: Path, rom_crc32: str
    ) -> Tuple[Dict[str, str], Optional[str]]:
        """Carrega overrides de texto PT-BR por chave/id."""
        for cand in self._candidate_strict_ptbr_override_paths(translated_path, rom_crc32):
            if not cand.exists():
                continue
            try:
                raw = json.loads(cand.read_text(encoding="utf-8"))
            except Exception:
                continue

            out: Dict[str, str] = {}
            if isinstance(raw, dict):
                for key, value in raw.items():
                    if isinstance(value, str):
                        out[str(key)] = value
                    elif isinstance(value, dict):
                        text = (
                            value.get("text")
                            or value.get("text_dst")
                            or value.get("translated")
                            or value.get("translation")
                        )
                        if isinstance(text, str):
                            out[str(key)] = text
            elif isinstance(raw, list):
                for item in raw:
                    if not isinstance(item, dict):
                        continue
                    key = item.get("key", item.get("id"))
                    if key is None:
                        continue
                    text = (
                        item.get("text")
                        or item.get("text_dst")
                        or item.get("translated")
                        or item.get("translation")
                    )
                    if isinstance(text, str):
                        out[str(key)] = text

            if out:
                return out, str(cand)
        return {}, None

    def _candidate_id_override_paths(
        self, translated_path: Path, rom_crc32: str
    ) -> List[Path]:
        """Lista caminhos candidatos para arquivo externo de override por ID."""
        policy = (
            self._translation_runtime_policy
            if isinstance(self._translation_runtime_policy, dict)
            else {}
        )
        raw_file = str(policy.get("id_override_file", "curated_fixes.json") or "").strip()
        crc = str(rom_crc32 or "").upper().strip()

        names = []
        if raw_file:
            names.append(raw_file)
        if crc:
            names.extend(
                [
                    f"{crc}_curated_fixes.json",
                    f"curated_fixes_{crc}.json",
                ]
            )
        names.append("curated_fixes.json")

        parent_candidates: List[Path] = [translated_path.parent]
        try:
            parent2 = translated_path.parent.parent
            if parent2.exists():
                parent_candidates.append(parent2)
                for rel in ("2_traducao", "3_reinsercao", "out", "1_extracao"):
                    cand_dir = parent2 / rel
                    if cand_dir.exists():
                        parent_candidates.append(cand_dir)
        except Exception:
            pass

        project_dir = self._project_root_dir()
        parent_candidates.extend(
            [
                project_dir,
                project_dir / "interface",
                project_dir / "core",
            ]
        )

        out: List[Path] = []
        seen = set()

        def _append_unique(cand_path: Path) -> None:
            try:
                rc = cand_path.resolve()
            except Exception:
                rc = cand_path
            if rc in seen:
                return
            seen.add(rc)
            out.append(cand_path)

        for name in names:
            p = Path(name)
            if p.is_absolute():
                _append_unique(p)
                continue
            for parent in parent_candidates:
                _append_unique(parent / name)

        return out

    def _extract_override_text(self, value: Any) -> Optional[str]:
        """Extrai string de override em formatos aceitos."""
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            for field in (
                "translated",
                "text_dst",
                "translation",
                "text",
                "value",
            ):
                text = value.get(field)
                if isinstance(text, str):
                    return text
        return None

    def _load_id_overrides(
        self, translated_path: Path, rom_crc32: str
    ) -> Tuple[Dict[str, str], Optional[str], List[str]]:
        """
        Carrega overrides externos por ID.

        Formatos aceitos:
        - {"511": "texto", "563": "texto"}
        - {"id_overrides": {"511": "texto"}}
        - {"overrides": [{"id": 511, "translated": "texto"}]}
        - [{"id": 511, "translated": "texto"}]
        """
        warnings: List[str] = []
        for cand in self._candidate_id_override_paths(translated_path, rom_crc32):
            if not cand.exists():
                continue
            try:
                raw = json.loads(cand.read_text(encoding="utf-8"))
            except Exception as exc:
                warnings.append(f"id_override_parse_error:{cand}:{exc}")
                continue

            payload: Any = raw
            if isinstance(raw, dict):
                for bucket in ("id_overrides", "overrides", "fixes", "entries"):
                    if bucket in raw and isinstance(raw.get(bucket), (dict, list)):
                        payload = raw.get(bucket)
                        break

            out: Dict[str, str] = {}
            dropped = 0

            if isinstance(payload, dict):
                for key, value in payload.items():
                    item_id = self._parse_optional_int_value(key)
                    if item_id is None and isinstance(value, dict):
                        item_id = self._parse_optional_int_value(
                            value.get("id", value.get("key"))
                        )
                    text = self._extract_override_text(value)
                    if item_id is None or not isinstance(text, str):
                        dropped += 1
                        continue
                    normalized = self._normalize_unicode_nfc(text).strip()
                    if not normalized:
                        dropped += 1
                        continue
                    out[str(int(item_id))] = normalized
            elif isinstance(payload, list):
                for item in payload:
                    if not isinstance(item, dict):
                        dropped += 1
                        continue
                    item_id = self._parse_optional_int_value(item.get("id", item.get("key")))
                    text = self._extract_override_text(item)
                    if item_id is None or not isinstance(text, str):
                        dropped += 1
                        continue
                    normalized = self._normalize_unicode_nfc(text).strip()
                    if not normalized:
                        dropped += 1
                        continue
                    out[str(int(item_id))] = normalized

            if dropped > 0:
                warnings.append(f"id_override_dropped_rows:{cand}:{dropped}")
            if out:
                return out, str(cand), warnings

        return {}, None, warnings

    def _build_ordered_translation_records(
        self,
        translated: Dict[str, str],
        fallback_entries: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Monta lista ordenada por seq (fallback: offset) para aplicação."""
        records: List[Dict[str, Any]] = []
        for idx, key in enumerate(translated.keys()):
            meta = fallback_entries.get(key, {}) if fallback_entries else {}
            seq_val = self._parse_optional_int_value(meta.get("seq"))
            off_val = self._parse_optional_int_value(
                meta.get("rom_offset", meta.get("offset", meta.get("origin_offset", meta.get("static_offset"))))
            )
            if off_val is None and isinstance(key, str):
                off_val = self._parse_optional_int_value(key)
            records.append(
                {
                    "key": key,
                    "seq": seq_val,
                    "offset": off_val if off_val is not None else -1,
                    "index": idx,
                }
            )

        records.sort(
            key=lambda rec: (
                0 if rec["seq"] is not None else 1,
                rec["seq"] if rec["seq"] is not None else rec["offset"],
                rec["offset"],
                rec["index"],
            )
        )
        return records

    def _build_ordered_meta_records(
        self,
        entries: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Ordena metadados por seq (fallback: offset) para checks."""
        ordered: List[Dict[str, Any]] = []
        for idx, (key, meta) in enumerate(entries.items()):
            if not isinstance(meta, dict):
                continue
            off_val = self._parse_optional_int_value(
                meta.get("rom_offset", meta.get("offset", meta.get("origin_offset", meta.get("static_offset"))))
            )
            if off_val is None and isinstance(key, str):
                off_val = self._parse_optional_int_value(key)
            if off_val is None:
                continue
            seq_val = self._parse_optional_int_value(meta.get("seq"))
            ordered.append(
                {
                    "key": key,
                    "seq": seq_val,
                    "offset": int(off_val),
                    "index": idx,
                }
            )

        ordered.sort(
            key=lambda rec: (
                0 if rec["seq"] is not None else 1,
                rec["seq"] if rec["seq"] is not None else rec["offset"],
                rec["offset"],
                rec["index"],
            )
        )
        return ordered

    def _infer_display_context_tag(
        self,
        meta: Optional[Dict[str, Any]],
        entry: Optional[MapEntry],
    ) -> str:
        """Infere tag de contexto para auditoria de cobertura."""
        if isinstance(meta, dict):
            for field in (
                "context_tag",
                "context",
                "scene",
                "dialog_context",
                "display_context",
                "screen",
                "stage",
                "source",
            ):
                raw = meta.get(field)
                if isinstance(raw, str) and raw.strip():
                    txt = re.sub(r"[^A-Za-z0-9_-]+", "_", raw.strip().lower())
                    txt = txt.strip("_")
                    if txt:
                        return txt[:48]
        if isinstance(entry, MapEntry):
            cat = str(entry.category or "").strip().lower()
            if cat:
                txt = re.sub(r"[^A-Za-z0-9_-]+", "_", cat).strip("_")
                if txt:
                    return txt[:48]
        return "dialog"

    def _write_jsonl_artifact_aliases(
        self,
        out_dir: Path,
        file_tags: List[str],
        suffix_name: str,
        rows: List[Dict[str, Any]],
        meta_record: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """Escreve JSONL com aliases por CRC (after/before/runtime)."""
        lines: List[str] = []
        if isinstance(meta_record, dict) and meta_record:
            lines.append(json.dumps(meta_record, ensure_ascii=False))
        for row in rows:
            lines.append(json.dumps(row, ensure_ascii=False))
        payload = "\n".join(lines).rstrip() + "\n"

        paths: Dict[str, str] = {}
        for tag in file_tags:
            path = out_dir / f"{tag}_{suffix_name}.jsonl"
            path.write_text(payload, encoding="utf-8")
            paths[str(tag)] = str(path)
        return paths

    def _write_json_artifact_aliases(
        self,
        out_dir: Path,
        file_tags: List[str],
        suffix_name: str,
        data: Dict[str, Any],
    ) -> Dict[str, str]:
        """Escreve JSON com aliases por CRC (after/before/runtime)."""
        payload = json.dumps(data, indent=2, ensure_ascii=False)
        paths: Dict[str, str] = {}
        for tag in file_tags:
            path = out_dir / f"{tag}_{suffix_name}.json"
            path.write_text(payload, encoding="utf-8")
            paths[str(tag)] = str(path)
        return paths

    def _build_display_trace_artifacts(
        self,
        ordered_keys: List[str],
        prepared_translated: Dict[str, str],
        items_report: List[Dict[str, Any]],
        fallback_entries: Optional[Dict[str, Dict[str, Any]]],
        issue_index_after: Dict[str, Any],
        translation_quality: Dict[str, Any],
        rom_before_bytes: bytes,
        runtime_crc32: str,
        runtime_size: int,
    ) -> Dict[str, Any]:
        """Gera tracer de cobertura exibível + faltantes (sem scan cego)."""
        fallback = fallback_entries if isinstance(fallback_entries, dict) else {}

        action_by_key: Dict[str, Dict[str, Any]] = {}
        for item in items_report:
            if not isinstance(item, dict):
                continue
            key = item.get("key")
            if key is None:
                continue
            k = str(key)
            action_by_key[k] = {
                "action": str(item.get("action", "") or ""),
                "reason": str(item.get("reason", "") or ""),
            }

        issue_keys_map: Dict[str, List[str]] = {}
        keys_by_category = (
            issue_index_after.get("keys_by_category", {})
            if isinstance(issue_index_after, dict)
            else {}
        )
        if isinstance(keys_by_category, dict):
            for cat, keys in keys_by_category.items():
                if not isinstance(keys, list):
                    continue
                for key in keys:
                    k = str(key)
                    issue_keys_map.setdefault(k, []).append(str(cat))

        trace_key_set: set = set()
        for key in ordered_keys or []:
            trace_key_set.add(str(key))
        for key in fallback.keys():
            trace_key_set.add(str(key))
        for item in items_report:
            if isinstance(item, dict) and item.get("key") is not None:
                trace_key_set.add(str(item.get("key")))

        sortable: List[Tuple[int, int, int, str]] = []
        for idx, key in enumerate(trace_key_set):
            meta = fallback.get(key, {}) if isinstance(fallback.get(key, {}), dict) else {}
            seq_val = self._parse_optional_int_value(meta.get("seq"))
            off_val = self._parse_optional_int_value(
                meta.get("rom_offset", meta.get("offset", meta.get("origin_offset")))
            )
            if off_val is None:
                entry = self.mapping.get(key)
                if isinstance(entry, MapEntry):
                    off_val = int(entry.offset)
            if off_val is None:
                off_val = self._parse_optional_int_value(key)
            if off_val is None:
                off_val = (1 << 30) + idx
            sortable.append(
                (
                    0 if seq_val is not None else 1,
                    int(seq_val if seq_val is not None else off_val),
                    int(off_val),
                    key,
                )
            )
        sortable.sort()

        def _norm_raw_hex(value: Any) -> str:
            raw = str(value or "").strip().replace(" ", "").replace("\t", "").upper()
            if not raw:
                return ""
            if not re.fullmatch(r"[0-9A-F]+", raw):
                return ""
            if len(raw) % 2 != 0:
                raw = raw[:-1]
            return raw

        trace_rows: List[Dict[str, Any]] = []
        missing_rows: List[Dict[str, Any]] = []
        mapped_count = 0
        unmapped_count = 0
        blocked_action_count = 0
        needs_review_count = 0
        display_candidate_count = 0
        display_excluded_nontext_count = 0
        visual_skip_displayed_count = 0
        visual_english_residual_count = 0
        visual_same_as_source_phrase_count = 0
        visual_skip_examples: List[Dict[str, Any]] = []
        visual_english_examples: List[Dict[str, Any]] = []

        for idx, (_, _, _, key) in enumerate(sortable):
            meta = fallback.get(key, {}) if isinstance(fallback.get(key, {}), dict) else {}
            entry = self.mapping.get(key)
            if entry is None and isinstance(meta, dict) and meta:
                entry = self._mapentry_from_jsonl(key, meta)
            mapping_found = bool(entry is not None)

            if mapping_found:
                mapped_count += 1
            else:
                unmapped_count += 1

            seq_val = self._parse_optional_int_value(meta.get("seq"))
            if seq_val is None:
                seq_val = idx
            off_val = self._parse_optional_int_value(
                meta.get("rom_offset", meta.get("offset", meta.get("origin_offset")))
            )
            if off_val is None and isinstance(entry, MapEntry):
                off_val = int(entry.offset)
            if off_val is None:
                off_val = self._parse_optional_int_value(key)
            off_hex = f"0x{int(off_val):06X}" if off_val is not None and int(off_val) >= 0 else None

            term_val = self._parse_optional_int_value(meta.get("terminator"))
            if term_val is None and isinstance(entry, MapEntry) and entry.terminator is not None:
                term_val = int(entry.terminator)

            raw_len = self._parse_optional_int_value(meta.get("raw_len"))
            raw_hex = _norm_raw_hex(meta.get("raw_bytes_hex"))
            if not raw_hex and isinstance(entry, MapEntry):
                read_len = raw_len if raw_len is not None and raw_len > 0 else int(entry.max_len)
                if term_val is not None:
                    read_len += 1
                start = int(entry.offset)
                if read_len > 0 and 0 <= start < len(rom_before_bytes):
                    end = min(len(rom_before_bytes), start + int(read_len))
                    raw_hex = bytes(rom_before_bytes[start:end]).hex().upper()
            if raw_len is None or raw_len <= 0:
                raw_len = len(raw_hex) // 2 if raw_hex else 0
                if raw_len <= 0 and isinstance(entry, MapEntry):
                    raw_len = int(entry.max_len) + (1 if term_val is not None else 0)

            review_flags_obj = meta.get("review_flags")
            if isinstance(review_flags_obj, list):
                review_flags = [str(flag) for flag in review_flags_obj if str(flag).strip()]
            elif isinstance(review_flags_obj, str) and review_flags_obj.strip():
                review_flags = [str(flag).strip() for flag in review_flags_obj.split(",") if str(flag).strip()]
            else:
                review_flags = []

            needs_review = bool(meta.get("needs_review", False)) or bool(review_flags)

            reinsertion_safe = (
                bool(meta.get("reinsertion_safe"))
                if "reinsertion_safe" in meta
                else bool(entry.reinsertion_safe if isinstance(entry, MapEntry) else False)
            )
            audit_roundtrip_ok = bool(meta.get("audit_roundtrip_ok", True))
            unknown_bytes_count = int(self._parse_optional_int_value(meta.get("unknown_bytes_count")) or 0)
            id_val = self._parse_optional_int_value(meta.get("id"))
            if id_val is None:
                id_val = self._parse_optional_int_value(key)

            action_info = action_by_key.get(key, {})
            action = str(action_info.get("action", "") or "")
            reason = str(action_info.get("reason", "") or "")
            action_upper = action.upper().strip()
            applied_actions = {
                "OK",
                "REPOINT",
                "REFORM",
                "WRAP",
                "FORCED",
                "SHORT",
                "DTE",
                "CMP_OK",
                "CMP_REPOINT",
                "CMP_REFORM",
                "CMP_WRAP",
                "CMP_REPOINT_WRAP",
                "CMP_SHORT",
                "CMP_REPOINT_SHORT",
            }
            effective_needs_review = bool(needs_review and action_upper not in applied_actions)
            if effective_needs_review:
                needs_review_count += 1
            issue_flags = sorted(set(issue_keys_map.get(key, [])))
            if action_upper.startswith("NOT_") or action_upper.startswith("SKIP_") or action_upper.startswith("BLOCKED_"):
                blocked_action_count += 1

            text_src = self._extract_source_text(meta)
            text_dst = str(prepared_translated.get(key, "") or "")
            context_tag = self._infer_display_context_tag(meta, entry)
            encoding = str(meta.get("encoding", entry.encoding if isinstance(entry, MapEntry) else "") or "").lower()
            is_tilemap = encoding in ("tile", "tilemap")
            non_plausible_meta = self._is_non_plausible_text_meta(meta)
            applied_now = action_upper in applied_actions
            source_nontext = self._is_probable_nontext_garbage(text_src)
            review_flags_upper = {str(f).strip().upper() for f in review_flags if str(f).strip()}
            src_compact = re.sub(r"\s+", " ", str(text_src or "")).strip()
            short_fragment_shard = (
                self._is_non_standalone_prefix_fragment(
                    src_compact,
                    review_flags=review_flags_upper,
                )
                and not applied_now
            )
            display_candidate = bool(
                applied_now
                or (
                    not non_plausible_meta
                    and not source_nontext
                    and not short_fragment_shard
                )
            )
            if display_candidate:
                display_candidate_count += 1
            else:
                display_excluded_nontext_count += 1
            is_skip_action = bool(
                action_upper.startswith("NOT_")
                or action_upper.startswith("SKIP_")
                or action_upper.startswith("BLOCKED_")
            )
            visual_skip_displayed = bool(display_candidate and is_skip_action)

            dst_lang = self._classify_language_line(text_dst) if text_dst.strip() else {}
            english_residual = bool(
                display_candidate
                and text_dst.strip()
                and (
                    bool(dst_lang.get("is_english", False))
                    or (
                        self._contains_english_stopwords(text_dst)
                        and not bool(dst_lang.get("is_ptbr", False))
                    )
                )
            )
            same_as_source_phrase = bool(
                display_candidate
                and text_dst.strip()
                and self._is_actionable_untranslated_same_source(text_src, text_dst)
            )
            if visual_skip_displayed:
                visual_skip_displayed_count += 1
                if len(visual_skip_examples) < 20:
                    visual_skip_examples.append(
                        {
                            "key": str(key),
                            "seq": int(seq_val),
                            "rom_offset": off_hex,
                            "context_tag": context_tag,
                            "last_action": action,
                            "last_reason": reason,
                            "text_src": str(text_src)[:140],
                            "text_dst": str(text_dst)[:140],
                        }
                    )
            if english_residual:
                visual_english_residual_count += 1
                if len(visual_english_examples) < 20:
                    visual_english_examples.append(
                        {
                            "key": str(key),
                            "seq": int(seq_val),
                            "rom_offset": off_hex,
                            "context_tag": context_tag,
                            "text_dst": str(text_dst)[:140],
                        }
                    )
            if same_as_source_phrase:
                visual_same_as_source_phrase_count += 1

            row = {
                "id": int(id_val) if id_val is not None else None,
                "key": str(key),
                "seq": int(seq_val),
                "rom_offset": off_hex,
                "raw_len": int(raw_len),
                "raw_bytes_hex": raw_hex,
                "terminator": int(term_val) if term_val is not None else None,
                "context_tag": context_tag,
                "encoding": encoding,
                "is_tilemap": bool(is_tilemap),
                "source": str(meta.get("source", entry.category if isinstance(entry, MapEntry) else "")),
                "text_src": text_src,
                "text_dst": text_dst,
                "mapping_found": bool(mapping_found),
                "mapping_status": "MAPPED" if mapping_found else "FALTANDO",
                "reinsertion_safe": bool(reinsertion_safe),
                "needs_review": bool(effective_needs_review),
                "display_candidate": bool(display_candidate),
                "review_flags": review_flags,
                "audit_roundtrip_ok": bool(audit_roundtrip_ok),
                "unknown_bytes_count": int(unknown_bytes_count),
                "last_action": action,
                "last_reason": reason,
                "visual_skip_displayed": bool(visual_skip_displayed),
                "english_residual": bool(english_residual),
                "same_as_source_phrase": bool(same_as_source_phrase),
                "issue_flags": issue_flags,
            }
            trace_rows.append(row)

            missing_reasons: List[str] = []
            if not mapping_found:
                missing_reasons.append("FALTANDO_MAPPING")
            if effective_needs_review:
                missing_reasons.append("NEEDS_REVIEW")
            if action_upper.startswith("NOT_") or action_upper.startswith("SKIP_") or action_upper.startswith("BLOCKED_"):
                missing_reasons.append("NOT_APPLIED")
            for issue in issue_flags:
                if issue:
                    missing_reasons.append(str(issue).upper())
            if visual_skip_displayed:
                missing_reasons.append("VISUAL_SKIP_DISPLAYED")
            if english_residual:
                missing_reasons.append("ENGLISH_RESIDUAL_DISPLAYED")
            if same_as_source_phrase:
                missing_reasons.append("SAME_AS_SOURCE_PHRASE_DISPLAYED")
            if not text_dst.strip():
                missing_reasons.append("TRANSLATION_EMPTY")
            if not display_candidate:
                missing_reasons = []

            if missing_reasons:
                missing_rows.append(
                    {
                        "id": row.get("id"),
                        "key": row.get("key"),
                        "seq": row.get("seq"),
                        "rom_offset": row.get("rom_offset"),
                        "context_tag": row.get("context_tag"),
                        "missing_reason_codes": sorted(set(missing_reasons)),
                        "mapping_found": row.get("mapping_found"),
                        "needs_review": row.get("needs_review"),
                        "last_action": row.get("last_action"),
                        "last_reason": row.get("last_reason"),
                        "review_flags": row.get("review_flags"),
                        "visual_skip_displayed": row.get("visual_skip_displayed"),
                        "english_residual": row.get("english_residual"),
                        "same_as_source_phrase": row.get("same_as_source_phrase"),
                        "issue_flags": row.get("issue_flags"),
                        "raw_len": row.get("raw_len"),
                        "raw_bytes_hex": row.get("raw_bytes_hex"),
                        "terminator": row.get("terminator"),
                        "reinsertion_safe": row.get("reinsertion_safe"),
                    }
                )

        coverage_summary = {
            "rom_crc32": str(runtime_crc32).upper(),
            "rom_size": int(runtime_size),
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "displayed_trace_items_total": int(len(trace_rows)),
            "displayed_trace_mapped_items": int(mapped_count),
            "displayed_trace_unmapped_items": int(unmapped_count),
            "display_candidate_items": int(display_candidate_count),
            "display_excluded_nontext_items": int(display_excluded_nontext_count),
            "displayed_trace_needs_review_items": int(needs_review_count),
            "displayed_trace_not_applied_items": int(blocked_action_count),
            "displayed_trace_skip_displayed_count": int(visual_skip_displayed_count),
            "displayed_trace_english_residual_count": int(visual_english_residual_count),
            "displayed_trace_same_as_source_phrase_count": int(visual_same_as_source_phrase_count),
            "missing_displayed_text_count": int(len(missing_rows)),
            "translation_quality_non_ptbr_suspect": int(
                (translation_quality or {}).get("non_ptbr_suspect", 0)
            ),
            "issue_index_counts": (
                issue_index_after.get("counts", {})
                if isinstance(issue_index_after, dict)
                else {}
            ),
            "coverage_target_reached": bool(len(missing_rows) == 0),
            "first_20_visual_skip_displayed": visual_skip_examples[:20],
            "first_20_english_residual": visual_english_examples[:20],
            "first_20_missing": missing_rows[:20],
        }

        return {
            "trace_rows": trace_rows,
            "missing_rows": missing_rows,
            "coverage_summary": coverage_summary,
        }

    # ---------- translated blocks ----------

    def load_translated_blocks(self, translated_path: Path) -> Dict[str, str]:
        """Lê arquivo no formato clean_blocks e retorna {key: texto}.

        Aceita cabeçalhos em dois formatos:
        - [key@...]
        - [key]
        """
        lines = translated_path.read_text(encoding="utf-8", errors="replace").splitlines()
        out: Dict[str, str] = {}

        key = None
        buf: List[str] = []

        def flush():
            nonlocal key, buf
            if key is not None:
                out[key] = self._normalize_unicode_nfc("\n".join(buf).rstrip("\n"))
            key, buf = None, []

        for ln in lines:
            if ln.startswith("[") and "]" in ln:
                # Cabeçalho válido se tiver "@" no mesmo line ou se não houver conteúdo após o "]"
                after = ln.split("]", 1)[1].strip()
                if "@" in ln or after == "":
                    flush()
                    key = ln.split("]", 1)[0].strip("[")
                    continue
            if ln.startswith("-") and set(ln.strip()) == {"-"}:
                flush()
                continue
            if key is not None:
                buf.append(ln)

        flush()
        if DEBUG:
            print(f"[DEBUG] SegaReinserter: loaded {len(out)} translated blocks from {translated_path.name}")
        return out

    # ---------- encoding ----------

    def _resolve_tbl_path_for_crc(self, crc32: Optional[str]) -> Optional[Path]:
        if not crc32:
            return None
        try:
            db_path = Path(__file__).parent / "game_profiles_db.json"
            if not db_path.exists():
                return None
            data = json.loads(db_path.read_text(encoding="utf-8"))
            for entry in data.get("games", []):
                if str(entry.get("crc32", "")).upper() == crc32.upper():
                    tbl_path = entry.get("tbl_path")
                    if not tbl_path:
                        return None
                    p = Path(tbl_path)
                    if p.is_absolute():
                        return p if p.exists() else None
                    # relativo ao projeto
                    project_dir = Path(__file__).parent.parent
                    candidate = project_dir / tbl_path
                    return candidate if candidate.exists() else None
        except Exception:
            return None
        return None

    def _should_strip_accents_for_crc(self, crc32: Optional[str]) -> bool:
        """Decide se deve remover acentos antes do fit/truncamento."""
        crc = str(crc32 or "").strip().upper()
        if not crc:
            return False
        if crc == "DE9F8517":
            return True
        try:
            db_path = Path(__file__).parent / "game_profiles_db.json"
            if not db_path.exists():
                return False
            data = json.loads(db_path.read_text(encoding="utf-8"))
            for entry in data.get("games", []):
                if str(entry.get("crc32", "")).upper() != crc:
                    continue
                if "font_has_pt_br" in entry:
                    return not bool(entry.get("font_has_pt_br"))
                return bool(self._coerce_bool(entry.get("strip_accents"), False))
        except Exception:
            return False
        return False

    def load_protected_regions(
        self,
        crc32: Optional[str],
        rom_size: Optional[int] = None,
    ) -> List[Tuple[int, int]]:
        """Carrega regiões protegidas do perfil do jogo em game_profiles_db.json."""
        if not crc32:
            return []
        try:
            db_path = Path(__file__).parent / "game_profiles_db.json"
            if not db_path.exists():
                return []
            data = json.loads(db_path.read_text(encoding="utf-8"))
        except Exception:
            return []

        game_entry: Optional[Dict[str, Any]] = None
        for entry in data.get("games", []):
            if str(entry.get("crc32", "")).upper() == str(crc32).upper():
                if isinstance(entry, dict):
                    game_entry = entry
                break
        if not isinstance(game_entry, dict):
            return []

        raw_regions = game_entry.get("protected_regions", [])
        if not isinstance(raw_regions, list):
            return []

        ranges: List[Tuple[int, int]] = []
        for region in raw_regions:
            start_val: Optional[int] = None
            end_val: Optional[int] = None
            if isinstance(region, (list, tuple)) and len(region) >= 2:
                start_val = self._parse_optional_int_value(region[0])
                end_val = self._parse_optional_int_value(region[1])
            elif isinstance(region, dict):
                start_val = self._parse_optional_int_value(
                    region.get("start", region.get("start_hex"))
                )
                end_val = self._parse_optional_int_value(
                    region.get("end", region.get("end_hex"))
                )
            if start_val is None or end_val is None:
                continue
            start_i = max(0, int(start_val))
            end_i = max(0, int(end_val))
            if rom_size is not None:
                start_i = min(start_i, int(rom_size))
                end_i = min(end_i, int(rom_size))
            if end_i <= start_i:
                continue
            ranges.append((start_i, end_i))

        if not ranges:
            return []
        ranges.sort(key=lambda item: (item[0], item[1]))
        merged: List[Tuple[int, int]] = [ranges[0]]
        for start_i, end_i in ranges[1:]:
            prev_start, prev_end = merged[-1]
            if start_i <= prev_end:
                merged[-1] = (prev_start, max(prev_end, end_i))
            else:
                merged.append((start_i, end_i))
        return merged

    def _merge_addr_ranges(self, ranges: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """Mescla ranges [start, end) garantindo ordenação e sem sobreposição."""
        valid: List[Tuple[int, int]] = []
        for start_val, end_val in ranges:
            try:
                start_i = int(start_val)
                end_i = int(end_val)
            except Exception:
                continue
            if end_i <= start_i:
                continue
            valid.append((start_i, end_i))
        if not valid:
            return []
        valid.sort(key=lambda item: (item[0], item[1]))
        merged: List[Tuple[int, int]] = [valid[0]]
        for start_i, end_i in valid[1:]:
            prev_start, prev_end = merged[-1]
            if start_i <= prev_end:
                merged[-1] = (prev_start, max(prev_end, end_i))
            else:
                merged.append((start_i, end_i))
        return merged

    def _collect_expected_mutable_ranges(
        self,
        rom_size: int,
        fallback_entries: Optional[Dict[str, Dict[str, Any]]],
    ) -> List[Tuple[int, int]]:
        """
        Coleta ranges que podem mudar legitimamente na reinserção:
        - slots de texto mapeados;
        - bytes de ponteiros mapeados (ptr_offset/pointer_offsets).
        """
        ranges: List[Tuple[int, int]] = []
        for key, entry in self.mapping.items():
            if not isinstance(entry, MapEntry):
                continue
            meta = (
                fallback_entries.get(str(key))
                if isinstance(fallback_entries, dict)
                else None
            )
            slot_len = int(
                self._resolve_entry_slot_total_len(
                    entry,
                    meta if isinstance(meta, dict) else None,
                )
            )
            start = max(0, int(entry.offset))
            end = min(int(rom_size), start + max(0, slot_len))
            if end > start:
                ranges.append((start, end))

            for ref in entry.pointer_refs or []:
                ptr_off = self._parse_optional_int_value(ref.get("ptr_offset"))
                ptr_size = self._parse_optional_int_value(ref.get("ptr_size"))
                if ptr_off is None:
                    continue
                p_start = max(0, int(ptr_off))
                p_len = int(ptr_size) if ptr_size is not None and int(ptr_size) > 0 else 2
                p_end = min(int(rom_size), p_start + p_len)
                if p_end > p_start:
                    ranges.append((p_start, p_end))

            for ptr_off in entry.pointer_offsets or []:
                p_val = self._parse_optional_int_value(ptr_off)
                if p_val is None:
                    continue
                p_start = max(0, int(p_val))
                p_end = min(int(rom_size), p_start + 2)
                if p_end > p_start:
                    ranges.append((p_start, p_end))

        return self._merge_addr_ranges(ranges)

    def _build_protected_backup(
        self,
        rom: bytearray,
        protected_regions: List[Tuple[int, int]],
        mutable_ranges: List[Tuple[int, int]],
    ) -> Tuple[Dict[int, int], int]:
        """
        Snapshot de regiões protegidas, excluindo ranges mutáveis esperados.
        Retorna (backup, bytes_excluidos).
        """
        if not protected_regions:
            return {}, 0

        merged_protected = self._merge_addr_ranges(protected_regions)
        merged_mutable = self._merge_addr_ranges(mutable_ranges)
        if not merged_mutable:
            backup = {
                int(addr): int(rom[addr])
                for start, end in merged_protected
                for addr in range(int(start), int(end))
                if 0 <= int(addr) < int(len(rom))
            }
            return backup, 0

        excluded_addrs: set = set()
        for p_start, p_end in merged_protected:
            for m_start, m_end in merged_mutable:
                if m_end <= p_start:
                    continue
                if m_start >= p_end:
                    break
                ov_start = max(int(p_start), int(m_start))
                ov_end = min(int(p_end), int(m_end))
                if ov_end > ov_start:
                    excluded_addrs.update(range(ov_start, ov_end))

        backup: Dict[int, int] = {}
        for start, end in merged_protected:
            for addr in range(int(start), int(end)):
                if addr in excluded_addrs:
                    continue
                if 0 <= int(addr) < int(len(rom)):
                    backup[int(addr)] = int(rom[int(addr)])
        return backup, int(len(excluded_addrs))

    def _enforce_protected_regions_integrity(
        self,
        rom: bytearray,
        original_rom: bytes,
        protected_regions: List[Tuple[int, int]],
        protected_backup: Dict[int, int],
        items_report: List[Dict[str, Any]],
        not_applied: List[Dict[str, Any]],
        stats: Dict[str, int],
        fallback_entries: Optional[Dict[str, Dict[str, Any]]],
        ) -> Dict[str, Any]:
        """Reverte escrita em regiões protegidas e marca blocos como bloqueados."""
        if not protected_regions or not protected_backup:
            return {
                "enabled": False,
                "protected_regions_count": 0,
                "protected_backup_bytes": 0,
                "changed_protected_bytes": 0,
                "reverted_blocks": 0,
                "reverted_bytes": 0,
                "remaining_changed_bytes": 0,
                "logs": [],
            }

        changed_addrs = sorted(
            addr
            for addr, original_byte in protected_backup.items()
            if 0 <= addr < len(rom) and int(rom[addr]) != int(original_byte)
        )
        if not changed_addrs:
            return {
                "enabled": True,
                "protected_regions_count": int(len(protected_regions)),
                "protected_backup_bytes": int(len(protected_backup)),
                "changed_protected_bytes": 0,
                "reverted_blocks": 0,
                "reverted_bytes": 0,
                "remaining_changed_bytes": 0,
                "logs": [],
            }

        block_candidates: List[Dict[str, Any]] = []
        for key, entry in self.mapping.items():
            if not isinstance(entry, MapEntry):
                continue
            meta_for_key = (
                fallback_entries.get(str(key))
                if isinstance(fallback_entries, dict)
                else None
            )
            slot_len = int(
                self._resolve_entry_slot_total_len(
                    entry,
                    meta_for_key if isinstance(meta_for_key, dict) else None,
                )
            )
            start = int(entry.offset)
            end = int(entry.offset) + max(0, slot_len)
            if start < len(original_rom) and end > start:
                block_candidates.append(
                    {
                        "key": str(key),
                        "start": max(0, start),
                        "end": min(int(end), int(len(original_rom))),
                    }
                )
            for ref in entry.pointer_refs or []:
                ptr_off = self._parse_optional_int_value(ref.get("ptr_offset"))
                ptr_size = self._parse_optional_int_value(ref.get("ptr_size"))
                if ptr_off is None:
                    continue
                ptr_size = int(ptr_size) if ptr_size is not None and int(ptr_size) > 0 else 2
                p_start = max(0, int(ptr_off))
                p_end = min(len(original_rom), p_start + ptr_size)
                if p_end > p_start:
                    block_candidates.append(
                        {"key": str(key), "start": p_start, "end": p_end}
                    )
            for ptr_off in entry.pointer_offsets or []:
                p_val = self._parse_optional_int_value(ptr_off)
                if p_val is None:
                    continue
                p_start = max(0, int(p_val))
                p_end = min(len(original_rom), p_start + 2)
                if p_end > p_start:
                    block_candidates.append(
                        {"key": str(key), "start": p_start, "end": p_end}
                    )

        block_candidates.sort(key=lambda row: (row["end"] - row["start"], row["start"]))
        reverted_keys: set = set()
        seen_blocked_keys: set = set()
        reverted_block_count = 0
        reverted_bytes = 0
        safe_logs: List[str] = []

        for addr in changed_addrs:
            matched = None
            for row in block_candidates:
                if row["start"] <= addr < row["end"]:
                    matched = row
                    break
            if matched is None:
                if 0 <= addr < len(original_rom):
                    rom[addr] = original_rom[addr]
                    reverted_bytes += 1
                msg = f"[SAFE] Bloco revertido — sobrescreveria byte protegido em 0x{addr:04X}"
                try:
                    print(msg)
                except Exception:
                    pass
                if len(safe_logs) < 128:
                    safe_logs.append(msg)
                continue

            key = str(matched.get("key", ""))
            start = int(matched["start"])
            end = int(matched["end"])
            if key in reverted_keys:
                continue
            reverted_keys.add(key)
            reverted_size = self.revert_block(
                rom=rom,
                original_rom=original_rom,
                start=start,
                end=end,
            )
            reverted_bytes += int(reverted_size)
            reverted_block_count += 1
            stats["SAFE_REVERT"] = int(stats.get("SAFE_REVERT", 0)) + 1
            stats["BLOCKED"] = int(stats.get("BLOCKED", 0)) + 1
            if key and key not in seen_blocked_keys:
                not_applied.append({"key": key, "reason": "protected_region_write"})
                seen_blocked_keys.add(key)
            items_report.append(
                {
                    "key": key,
                    "action": "SAFE_REVERT",
                    "offset": start,
                    "max_len": max(0, end - start),
                    "reason": "protected_region_write",
                    "protected_byte": f"0x{addr:04X}",
                }
            )
            msg = f"[SAFE] Bloco revertido — sobrescreveria byte protegido em 0x{addr:04X}"
            try:
                print(msg)
            except Exception:
                pass
            if len(safe_logs) < 128:
                safe_logs.append(msg)

        remaining_changed = [
            addr
            for addr, original_byte in protected_backup.items()
            if 0 <= addr < len(rom) and int(rom[addr]) != int(original_byte)
        ]
        if remaining_changed:
            for addr in remaining_changed:
                if 0 <= addr < len(original_rom):
                    rom[addr] = original_rom[addr]
                    reverted_bytes += 1
            stats["SAFE_REVERT_BYTE_FALLBACK"] = int(
                stats.get("SAFE_REVERT_BYTE_FALLBACK", 0)
            ) + int(len(remaining_changed))
            if len(safe_logs) < 128:
                safe_logs.append(
                    "[SAFE] Ajuste byte-a-byte aplicado para finalizar proteção de regiões críticas."
                )

        return {
            "enabled": True,
            "protected_regions_count": int(len(protected_regions)),
            "protected_backup_bytes": int(len(protected_backup)),
            "changed_protected_bytes": int(len(changed_addrs)),
            "reverted_blocks": int(reverted_block_count),
            "reverted_bytes": int(reverted_bytes),
            "remaining_changed_bytes": int(len(remaining_changed)),
            "logs": safe_logs,
        }

    def revert_block(
        self,
        rom: bytearray,
        original_rom: bytes,
        start: int,
        end: int,
    ) -> int:
        """Restaura bloco [start,end) da ROM original e retorna bytes revertidos."""
        try:
            start_i = max(0, int(start))
            end_i = max(0, int(end))
        except Exception:
            return 0
        if end_i <= start_i:
            return 0
        if start_i >= len(rom) or start_i >= len(original_rom):
            return 0
        end_i = min(end_i, len(rom), len(original_rom))
        if end_i <= start_i:
            return 0
        rom[start_i:end_i] = original_rom[start_i:end_i]
        return int(end_i - start_i)

    def _range_overlaps_any(
        self,
        start: int,
        end: int,
        ranges: List[Tuple[int, int]],
    ) -> bool:
        """Retorna True se [start,end) cruza qualquer faixa protegida."""
        try:
            s = int(start)
            e = int(end)
        except Exception:
            return False
        if e <= s:
            return False
        for r_start, r_end in ranges:
            try:
                rs = int(r_start)
                re_ = int(r_end)
            except Exception:
                continue
            if re_ <= rs:
                continue
            if not (e <= rs or s >= re_):
                return True
        return False

    def _build_runtime_ascii_tbl_loader(self):
        """
        Constrói uma TBL ASCII mínima em memória.
        Usada quando o perfil não possui tbl_path, permitindo:
        - detectar caracteres ausentes para glyph injection;
        - codificar acentos mapeados em tempo de execução.
        """
        try:
            from core.tbl_loader import TBLLoader
        except Exception:
            try:
                from tbl_loader import TBLLoader
            except Exception:
                return None
        try:
            tbl = TBLLoader()
            for code in range(0x20, 0x7F):
                ch = chr(code)
                tbl.char_map[int(code)] = ch
                tbl.reverse_map[ch] = bytes([int(code)])
            tbl.max_entry_len = 1
            setattr(tbl, "_neurorom_runtime_ascii", True)
            return tbl
        except Exception:
            return None

    def _get_tbl_loader(self, require_tilemap: bool = False):
        if self._tbl_loader is not None:
            if require_tilemap and getattr(self._tbl_loader, "_neurorom_runtime_ascii", False):
                return None
            return self._tbl_loader
        tbl_path = self._resolve_tbl_path_for_crc(self.mapping_crc32)
        if not tbl_path:
            enable_runtime_ascii = os.environ.get("NEUROROM_RUNTIME_ASCII_TBL", "1") == "1"
            if enable_runtime_ascii:
                self._tbl_loader = self._build_runtime_ascii_tbl_loader()
                if self._tbl_loader is not None:
                    self._tile_entry_len = 1
                    self._tile_space_seq = self._tbl_loader.reverse_map.get(" ")
            if require_tilemap and getattr(self._tbl_loader, "_neurorom_runtime_ascii", False):
                return None
            return self._tbl_loader
        try:
            from core.tbl_loader import TBLLoader
        except Exception:
            return None
        try:
            self._tbl_loader = TBLLoader(str(tbl_path))
            self._tile_entry_len = max(1, int(getattr(self._tbl_loader, "max_entry_len", 1)))
            self._tile_space_seq = self._tbl_loader.reverse_map.get(" ")
        except Exception:
            self._tbl_loader = None
        if require_tilemap and getattr(self._tbl_loader, "_neurorom_runtime_ascii", False):
            return None
        return self._tbl_loader

    def _sanitize_tilemap_text(self, text: str, reverse_map: Dict[str, bytes]) -> str:
        """Normaliza texto para caber no charset tilemap (sem acentos, uppercase)."""
        cleaned, _ = self._sanitize_tilemap_text_with_fallback(text, reverse_map)
        return cleaned

    def _sanitize_tilemap_text_with_fallback(
        self, text: str, reverse_map: Dict[str, bytes]
    ) -> Tuple[str, int]:
        """Normaliza texto para caber no charset tilemap e conta fallback."""
        if not text:
            return "", 0
        norm = unicodedata.normalize("NFD", text)
        norm = "".join(ch for ch in norm if unicodedata.category(ch) != "Mn")
        norm = norm.upper().replace("\r", "").replace("\n", " ")
        out: List[str] = []
        fallback = 0
        space_fallback = " " if " " in reverse_map else ""
        for ch in norm:
            if ch in reverse_map:
                out.append(ch)
            else:
                if ch.strip():
                    fallback += 1
                out.append(space_fallback)
        return "".join(out), fallback

    def _encode_tilemap_lowbytes(self, s: str, reverse_map: Dict[str, bytes]) -> bytes:
        """Codifica texto em low-bytes (preserva atributos originais na reinserção)."""
        cleaned = self._sanitize_tilemap_text(s, reverse_map)
        out = bytearray()
        space_seq = reverse_map.get(" ")
        space_low = space_seq[0] if space_seq else 0x00
        for ch in cleaned:
            seq = reverse_map.get(ch)
            if seq is None:
                out.append(space_low)
            else:
                out.append(seq[0])
        return bytes(out)

    def _encode(self, s: str, encoding: str) -> bytes:
        # Se TBL está carregado e tem mapeamento não-ASCII (offset != 0),
        # usar TBL mesmo para entries "ascii" — o jogo usa encoding customizada
        if encoding not in ("tile", "tilemap"):
            tbl = self._get_tbl_loader()
            if tbl:
                reverse_map = getattr(tbl, "reverse_map", {})
                # Detecta se TBL tem offset (ex: espaço mapeado para 0x00 em vez de 0x20)
                space_seq = reverse_map.get(" ")
                if space_seq and len(space_seq) == 1 and space_seq[0] != 0x20:
                    # TBL com offset customizado — usar TBL para codificar
                    s = s.replace("\r\n", "\n")
                    encoded = bytearray()
                    for ch in s:
                        seq = reverse_map.get(ch)
                        if seq is None:
                            seq = reverse_map.get(" ")
                        if seq is None:
                            encoded.append(0x00)
                        else:
                            encoded.extend(seq)
                    return bytes(encoded)
            s = s.replace("\r\n", "\n")
            return s.encode("ascii", errors="replace")

        # Tilemap (usa TBL multi-byte quando disponível)
        tbl = self._get_tbl_loader(require_tilemap=True)
        if not tbl:
            # fallback ASCII para não quebrar execução
            s = s.replace("\r\n", "\n")
            return s.encode("ascii", errors="replace")

        reverse_map = getattr(tbl, "reverse_map", {})
        cleaned = self._sanitize_tilemap_text(s, reverse_map)
        encoded = bytearray()
        for ch in cleaned:
            seq = reverse_map.get(ch)
            if seq is None:
                seq = reverse_map.get(" ")
            if seq is None:
                continue
            encoded.extend(seq)
        return bytes(encoded)

    def _sanitize_ascii_text(self, text: str) -> str:
        """Sanitiza texto ASCII (remove acentos e normaliza aspas)."""
        cleaned, _ = self._sanitize_ascii_text_with_fallback(text)
        return cleaned

    def _sanitize_ascii_text_with_fallback(
        self,
        text: str,
        preserve_newlines: bool = False,
        preserve_diacritics: bool = False,
    ) -> Tuple[str, int]:
        """Sanitiza texto ASCII e conta fallback de charset."""
        if not text:
            return "", 0
        if preserve_diacritics:
            norm = unicodedata.normalize("NFC", text)
        else:
            norm = unicodedata.normalize("NFD", text)
            norm = "".join(ch for ch in norm if unicodedata.category(ch) != "Mn")
        norm = (
            norm.replace("“", "\"")
            .replace("”", "\"")
            .replace("‘", "'")
            .replace("’", "'")
            .replace("—", "-")
            .replace("–", "-")
            .replace("…", "...")
        )
        norm = norm.replace("\r", "")
        if not preserve_newlines:
            norm = norm.replace("\n", " ")
        allowed = {chr(i) for i in range(32, 127)}
        if preserve_diacritics:
            tbl = self._get_tbl_loader()
            reverse_map = getattr(tbl, "reverse_map", {}) if tbl else {}
            if isinstance(reverse_map, dict):
                for ch, seq in reverse_map.items():
                    if (
                        isinstance(ch, str)
                        and len(ch) == 1
                        and isinstance(seq, (bytes, bytearray))
                        and len(seq) == 1
                    ):
                        allowed.add(ch)
        if preserve_newlines:
            allowed.add("\n")
        out = []
        fallback = 0
        for ch in norm:
            if ch in allowed:
                out.append(ch)
            else:
                if ch.strip():
                    fallback += 1
                out.append(" ")
        return "".join(out), fallback

    def _encode_ascii_chunk_with_optional_tbl(
        self,
        text: str,
        preserve_newlines: bool = False,
    ) -> Tuple[bytes, int, str]:
        """
        Codifica chunk ASCII preservando caracteres acentuados quando houver
        mapeamento de 1 byte no TBL ativo.
        """
        if not text:
            return b"", 0, ""

        tbl = self._get_tbl_loader()
        reverse_map = getattr(tbl, "reverse_map", {}) if tbl else {}
        single_byte_map: Dict[str, int] = {}
        if isinstance(reverse_map, dict):
            for ch, seq in reverse_map.items():
                if not isinstance(ch, str) or len(ch) != 1:
                    continue
                if not isinstance(seq, (bytes, bytearray)) or len(seq) != 1:
                    continue
                byte_val = int(seq[0]) & 0xFF
                # Segurança: evita mapear para bytes de controle (<0x20),
                # pois podem quebrar layout/script em entradas ASCII.
                if byte_val < 0x20:
                    continue
                single_byte_map[ch] = byte_val

        norm = unicodedata.normalize("NFC", text)
        norm = (
            norm.replace("“", "\"")
            .replace("”", "\"")
            .replace("‘", "'")
            .replace("’", "'")
            .replace("—", "-")
            .replace("–", "-")
            .replace("…", "...")
        )
        norm = norm.replace("\r", "")
        if not preserve_newlines:
            norm = norm.replace("\n", " ")

        out = bytearray()
        sanitized: List[str] = []
        fallback = 0
        for ch in norm:
            if preserve_newlines and ch == "\n":
                out.append(0x0A)
                sanitized.append(ch)
                continue

            code = ord(ch)
            if 32 <= code <= 126:
                out.append(code)
                sanitized.append(ch)
                continue

            mapped = single_byte_map.get(ch)
            if mapped is not None:
                out.append(mapped)
                sanitized.append(ch)
                continue

            # Fallback robusto: tenta transliterar (ã->a, ç->c, é->e, etc.)
            # para evitar lacunas visuais como "N o" quando o glyph não existe.
            ascii_fallback = ""
            decomp = unicodedata.normalize("NFD", ch)
            for dch in decomp:
                if unicodedata.category(dch) == "Mn":
                    continue
                code_dch = ord(dch)
                if 32 <= code_dch <= 126:
                    ascii_fallback = dch
                    break
            if ascii_fallback:
                out.append(ord(ascii_fallback))
                sanitized.append(ascii_fallback)
                continue

            if ch.strip():
                fallback += 1
            out.append(0x20)
            sanitized.append(" ")

        return bytes(out), int(fallback), "".join(sanitized)

    def _encode_ascii_with_byte_placeholders(
        self,
        text: str,
        preserve_newlines: bool = False,
    ) -> Tuple[bytes, int, str]:
        """
        Converte texto ASCII para bytes preservando tokens ``{B:XX}`` como byte real.
        Retorna: (payload_bytes, fallback_chars, texto_sanitizado_para_log).
        """
        if not isinstance(text, str) or not text:
            return b"", 0, ""

        encoded = bytearray()
        fallback_total = 0
        sanitized_parts: List[str] = []
        last = 0

        for match in self._byte_placeholder_re.finditer(text):
            chunk = text[last:match.start()]
            if chunk:
                chunk_bytes, fb, clean = self._encode_ascii_chunk_with_optional_tbl(
                    chunk, preserve_newlines=preserve_newlines
                )
                fallback_total += int(fb)
                sanitized_parts.append(clean)
                encoded.extend(chunk_bytes)

            token = match.group(0)
            hex_part = match.group(1)
            try:
                byte_val = int(hex_part, 16) & 0xFF
                encoded.append(byte_val)
                sanitized_parts.append(token)
            except ValueError:
                # Token inválido: trata como texto normal, sem quebrar pipeline.
                token_bytes, fb_token, clean_token = self._encode_ascii_chunk_with_optional_tbl(
                    token, preserve_newlines=preserve_newlines
                )
                fallback_total += int(fb_token)
                sanitized_parts.append(clean_token)
                encoded.extend(token_bytes)

            last = match.end()

        tail = text[last:]
        if tail:
            tail_bytes, fb_tail, clean_tail = self._encode_ascii_chunk_with_optional_tbl(
                tail, preserve_newlines=preserve_newlines
            )
            fallback_total += int(fb_tail)
            sanitized_parts.append(clean_tail)
            encoded.extend(tail_bytes)

        sanitized_text = "".join(sanitized_parts)
        return bytes(encoded), int(fallback_total), sanitized_text

    def _is_ui_meta_entry(self, meta: Optional[Dict[str, Any]], source_hint: str = "") -> bool:
        """Detecta item de UI enriquecido pelo extractor."""
        if isinstance(meta, dict):
            if bool(meta.get("ui_item", False)):
                return True
            src = str(meta.get("source", source_hint) or source_hint)
            if src.startswith("UI_POINTER_"):
                return True
        return str(source_hint or "").startswith("UI_POINTER_")

    def _normalize_ui_block_reason(self, reason: str) -> str:
        """Padroniza códigos de bloqueio de UI para auditoria."""
        code = str(reason or "").strip().upper()
        if not code:
            return "POINTER_INVALID"
        mapping = {
            "TOKEN_MISMATCH": "TOKEN_MISMATCH",
            "INVALID_CHARSET": "INVALID_CHARSET",
            "TERMINATOR_MISSING": "TERMINATOR_MISSING",
            "TERMINATOR_IN_PAYLOAD": "TERMINATOR_MISSING",
            "TERMINATOR_WRITE_OOB": "TERMINATOR_MISSING",
            "POINTER_INVALID": "POINTER_INVALID",
            "BYTE_OVERFLOW": "BYTE_OVERFLOW",
            "LAYOUT_OVERFLOW": "BYTE_OVERFLOW",
            "REPOINT_FAILED_NO_SPACE": "POINTER_INVALID",
            "POINTER_WRITE_FAILED": "POINTER_INVALID",
            "NO_POINTER_SOURCES": "POINTER_INVALID",
            "POINTER_OVERFLOW_OR_MISSING": "POINTER_INVALID",
            "NEEDS_REVIEW": "POINTER_INVALID",
            "REINSERTION_SAFE=FALSE": "POINTER_INVALID",
            "REINSERTION_SAFE_FALSE": "POINTER_INVALID",
            "MAPPING NÃO ENCONTRADO": "POINTER_INVALID",
            "MAPPING NAO ENCONTRADO": "POINTER_INVALID",
            "OVERLAP_EXISTING_RANGE": "POINTER_INVALID",
            "CHARMAP_MISMATCH": "INVALID_CHARSET",
        }
        if code in mapping:
            return mapping[code]
        if "MAPPING" in code or "POINTER" in code:
            return "POINTER_INVALID"
        return "POINTER_INVALID"

    def _extract_ui_reason_from_item_report(self, item: Dict[str, Any]) -> str:
        """Extrai motivo de bloqueio de item_report em formato auditável para UI."""
        if not isinstance(item, dict):
            return "POINTER_INVALID"
        reason_obj = item.get("reason")
        if isinstance(reason_obj, str) and reason_obj.strip():
            return self._normalize_ui_block_reason(reason_obj)
        errors_obj = item.get("errors")
        if isinstance(errors_obj, list) and errors_obj:
            first = str(errors_obj[0] or "")
            if first.strip():
                return self._normalize_ui_block_reason(first)
        action = str(item.get("action", "") or "").strip()
        if action:
            return self._normalize_ui_block_reason(action)
        return "POINTER_INVALID"

    def _parse_ui_template_bytes(self, meta: Optional[Dict[str, Any]]) -> Optional[bytes]:
        if not isinstance(meta, dict):
            return None
        for key in ("ui_template_hex", "raw_bytes_hex"):
            value = str(meta.get(key, "") or "").strip().replace(" ", "").upper()
            if not value:
                continue
            if not re.fullmatch(r"[0-9A-F]+", value):
                continue
            if len(value) % 2 != 0:
                value = value[:-1]
            if not value:
                continue
            try:
                return bytes.fromhex(value)
            except Exception:
                continue
        return None

    def _resolve_template_writable_positions(
        self,
        meta: Optional[Dict[str, Any]],
        template: bytes,
    ) -> List[int]:
        """Resolve posições imprimíveis onde a tradução pode ser escrita."""
        if not isinstance(template, (bytes, bytearray)) or not template:
            return []
        printable_positions_obj = meta.get("ui_printable_positions") if isinstance(meta, dict) else None
        printable_positions: List[int] = []
        if isinstance(printable_positions_obj, list):
            for pos in printable_positions_obj:
                p = self._parse_optional_int_value(pos)
                if p is None:
                    continue
                p_i = int(p)
                if 0 <= p_i < len(template):
                    printable_positions.append(p_i)
        if not printable_positions:
            printable_positions = [idx for idx, b in enumerate(template) if 0x20 <= int(b) <= 0x7E]
        if not printable_positions:
            return []
        writable_positions = list(printable_positions)

        source_hint = ""
        if isinstance(meta, dict):
            source_hint = str(
                meta.get("text_src")
                or meta.get("text")
                or meta.get("original_text")
                or ""
            )
        if source_hint:
            source_folded = self._fold_text_to_ascii_for_ui(source_hint)
            source_folded = re.sub(r"\s+", " ", source_folded).strip()
            template_printable = "".join(chr(template[idx]) for idx in printable_positions)
            if source_folded and template_printable.endswith(source_folded):
                shift = max(0, len(template_printable) - len(source_folded))
                if shift > 0 and shift < len(writable_positions):
                    writable_positions = writable_positions[shift:]
            elif source_folded:
                compact_template = re.sub(r"\s+", "", template_printable).lower()
                compact_source = re.sub(r"\s+", "", source_folded).lower()
                pos_compact = compact_template.find(compact_source) if compact_source else -1
                if pos_compact > 0 and pos_compact < len(writable_positions):
                    writable_positions = writable_positions[pos_compact:]

        # Alguns templates ASCII_CTRL têm prefixo oculto (ex.: "P<ctrl>Options").
        # Não sobrescrever esse byte evita sumiço da 1ª letra visível.
        if (
            len(writable_positions) >= 2
            and writable_positions[0] == 0
            and writable_positions[1] > 1
            and len(template) > 1
            and int(template[1]) < 0x20
            and int(template[0]) in (0x50, 0x70, 0x22, 0x27)  # "P"/"p"/quotes
        ):
            writable_positions = writable_positions[1:]
        return writable_positions

    def _resolve_entry_terminator(
        self,
        entry: Optional[MapEntry],
        meta: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """Resolve terminador priorizando JSONL, com fallback no mapping."""
        term_val = None
        if isinstance(meta, dict):
            term_val = self._parse_optional_int_value(meta.get("terminator"))
            if term_val is None and meta.get("terminator_hex") is not None:
                term_val = self._parse_optional_int_value(meta.get("terminator_hex"))
        if term_val is None and isinstance(entry, MapEntry) and entry.terminator is not None:
            term_val = int(entry.terminator)
        if term_val is None:
            return None
        term_val = int(term_val) & 0xFF
        if isinstance(entry, MapEntry):
            entry.terminator = int(term_val)
        return int(term_val)

    def _is_control_template_entry(
        self,
        entry: Optional[MapEntry],
        meta: Optional[Dict[str, Any]],
    ) -> bool:
        """Detecta entrada ASCII com bytes de controle que exige preservação de template."""
        if not isinstance(entry, MapEntry):
            return False
        if str(entry.encoding or "").strip().lower() != "ascii_ctrl_prefixed":
            return False
        return self._parse_ui_template_bytes(meta) is not None

    def _fold_text_to_ascii_for_ui(self, text: str) -> str:
        """
        Converte texto para ASCII seguro de UI sem quebrar placeholders {B:XX}.
        Usado como fallback quando há INVALID_CHARSET em entradas UI.
        """
        if not isinstance(text, str) or not text:
            return ""
        folded, _ = self._sanitize_ascii_text_with_fallback(
            text,
            preserve_newlines=False,
            preserve_diacritics=False,
        )
        return re.sub(r"\s+", " ", folded).strip()

    def _build_ui_payload_with_template(
        self,
        text: str,
        meta: Optional[Dict[str, Any]],
        term_value: Optional[int],
    ) -> Tuple[Optional[bytes], int, str, Optional[str]]:
        """
        Monta payload preservando bytes de controle do template de UI.
        Retorna (payload, fallback_chars, sanitized_text, erro).
        """
        template = self._parse_ui_template_bytes(meta)
        if not template:
            return None, 0, "", "POINTER_INVALID"

        writable_positions = self._resolve_template_writable_positions(meta, template)
        if not writable_positions:
            return None, 0, "", "INVALID_CHARSET"

        term_byte = None
        if term_value is not None:
            term_byte = int(term_value) & 0xFF
            if term_byte in template:
                return None, 0, "", "TERMINATOR_MISSING"

        def _encode_ui_text(raw_text: str) -> Tuple[bytes, int, str]:
            safe_text = self._fold_text_to_ascii_for_ui(raw_text)
            if not safe_text and raw_text:
                safe_text = str(raw_text)
            encoded_local, fallback_local, sanitized_local = self._encode_ascii_with_byte_placeholders(
                safe_text,
                preserve_newlines=False,
            )
            if int(fallback_local) <= 0:
                return encoded_local, int(fallback_local), sanitized_local

            # Fallback de robustez: remove diacríticos para não bloquear a linha UI.
            folded_text = self._fold_text_to_ascii_for_ui(raw_text)
            if folded_text and folded_text != raw_text:
                encoded_folded, fallback_folded, sanitized_folded = self._encode_ascii_with_byte_placeholders(
                    folded_text,
                    preserve_newlines=False,
                )
                if int(fallback_folded) <= 0:
                    return encoded_folded, int(fallback_folded), sanitized_folded
            return encoded_local, int(fallback_local), sanitized_local

        encoded_text, fallback_cnt, sanitized = _encode_ui_text(str(text or ""))
        if fallback_cnt > 0:
            return None, int(fallback_cnt), sanitized, "INVALID_CHARSET"
        if term_byte is not None and bytes([term_byte]) in encoded_text:
            return None, int(fallback_cnt), sanitized, "TERMINATOR_MISSING"
        if len(encoded_text) > len(writable_positions):
            # Ajuste cirúrgico para UI: compacta ao limite do template antes de bloquear.
            slot_len = max(0, int(len(writable_positions)))
            fitted_text = self._fold_text_to_ascii_for_ui(str(text or ""))
            fitted_text = self._apply_short_style_sanitization(fitted_text)
            if slot_len > 0:
                fitted_text = re.sub(r"\s*([,.;:!?])\s*", r"\1", fitted_text)
                fitted_text = re.sub(r"\s+", " ", fitted_text).strip()
                if len(fitted_text) > slot_len:
                    shortened = self._shorten_wordwise(fitted_text, slot_len)
                    if isinstance(shortened, str) and shortened.strip():
                        fitted_text = shortened.strip()
                if len(fitted_text) > slot_len:
                    fitted_text = fitted_text[:slot_len]
            encoded_fit, fallback_fit, sanitized_fit = _encode_ui_text(fitted_text)
            if fallback_fit > 0:
                return None, int(fallback_fit), sanitized_fit, "INVALID_CHARSET"
            if term_byte is not None and bytes([term_byte]) in encoded_fit:
                return None, int(fallback_fit), sanitized_fit, "TERMINATOR_MISSING"
            if len(encoded_fit) > len(writable_positions):
                return None, int(fallback_fit), sanitized_fit, "BYTE_OVERFLOW"
            encoded_text = encoded_fit
            fallback_cnt = int(fallback_fit)
            sanitized = sanitized_fit

        payload = bytearray(template)
        for idx, pos in enumerate(writable_positions):
            payload[pos] = encoded_text[idx] if idx < len(encoded_text) else 0x20

        if term_byte is not None and term_byte in payload:
            return None, int(fallback_cnt), sanitized, "TERMINATOR_MISSING"

        return bytes(payload), int(fallback_cnt), sanitized, None

    def _normalize_compare_text(self, text: str) -> str:
        """Normaliza texto para comparação sem ruído."""
        if not isinstance(text, str):
            return ""
        text = unicodedata.normalize("NFD", text)
        text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
        text = text.lower()
        text = re.sub(r"[^a-z0-9]+", "", text)
        return text

    def _classify_language_line(self, text: str) -> Dict[str, Any]:
        """Heurística simples para auditar se linha parece PT-BR ou EN."""
        raw = text if isinstance(text, str) else ""
        lowered = raw.lower()
        words = [w.lower() for w in self._word_re.findall(lowered)]
        letters = sum(1 for ch in raw if ch.isalpha())
        alpha_ratio = letters / max(1, len(raw.strip())) if raw.strip() else 0.0
        if not words:
            return {
                "is_ptbr": False,
                "is_english": False,
                "is_noise": True,
                "pt_score": 0,
                "en_score": 0,
                "word_count": 0,
                "alpha_ratio": alpha_ratio,
            }
        pt_hits = sum(1 for w in words if w in self._pt_hint_words)
        en_hits = sum(1 for w in words if w in self._en_hint_words)
        pt_suffix_hits = sum(
            1
            for w in words
            if w.endswith(
                (
                    "cao", "coes", "mente", "ndo", "ria", "rias", "zinho", "zinha",
                    "dade", "tude", "ario", "aria", "eiro", "eira", "agem", "ivel",
                    "avel", "oso", "osa", "ico", "ica", "ado", "ada", "ido", "ida",
                    "nte", "ncia", "sao", "ao", "oes",
                )
            )
        )
        accent_bonus = 1 if any(ch in lowered for ch in ("ã", "õ", "ç", "á", "é", "í", "ó", "ú")) else 0
        short_line_bonus = 1 if en_hits == 0 and 2 <= len(words) <= 3 else 0
        pt_score = pt_hits + accent_bonus + (1 if pt_suffix_hits > 0 else 0) + short_line_bonus
        en_score = en_hits
        noise_like = bool(alpha_ratio < 0.45 and pt_hits == 0 and en_hits == 0)
        is_english = en_score >= 2 and en_score > pt_score
        is_ptbr = (
            (pt_score >= 1 and pt_score >= en_score)
            or (en_score == 0 and len(words) <= 3)
            or (noise_like and en_score == 0)
        )
        return {
            "is_ptbr": is_ptbr,
            "is_english": is_english,
            "is_noise": noise_like,
            "pt_score": pt_score,
            "en_score": en_score,
            "word_count": len(words),
            "alpha_ratio": round(alpha_ratio, 4),
        }

    def _build_translation_audit(
        self,
        translated: Dict[str, str],
        fallback_entries: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Gera evidências de qualidade da tradução para report/proof."""
        audit = {
            "total_lines": len(translated),
            "ignored_non_plausible": 0,
            "ignored_prefix_fragment": 0,
            "ptbr_likely": 0,
            "english_likely": 0,
            "non_ptbr_suspect": 0,
            "same_as_source": 0,
            "empty": 0,
            "examples": {
                "english_likely": [],
                "non_ptbr_suspect": [],
                "same_as_source": [],
            },
        }
        for key, dst in translated.items():
            dst_text = dst if isinstance(dst, str) else ""
            if not dst_text.strip():
                audit["empty"] += 1
                continue
            meta = fallback_entries.get(key) if fallback_entries else {}
            if self._is_non_plausible_text_meta(meta):
                audit["ignored_non_plausible"] += 1
            src_meta = self._extract_source_text(meta)
            if self._is_non_standalone_prefix_fragment(
                src_meta or dst_text,
                set(self._normalized_review_flags(meta)),
            ):
                audit["ignored_prefix_fragment"] += 1
            if self._is_probable_nontext_garbage(dst_text) and not self._looks_phrase_like_text(dst_text):
                continue

            info = self._classify_language_line(dst_text)
            if info["is_ptbr"]:
                audit["ptbr_likely"] += 1
            if info["is_english"]:
                audit["english_likely"] += 1
                if len(audit["examples"]["english_likely"]) < 8:
                    audit["examples"]["english_likely"].append(
                        {"key": key, "text": dst_text[:120]}
                    )
            if (not info["is_ptbr"]) and (not info.get("is_noise", False)) and info["word_count"] >= 2:
                audit["non_ptbr_suspect"] += 1
                if len(audit["examples"]["non_ptbr_suspect"]) < 8:
                    audit["examples"]["non_ptbr_suspect"].append(
                        {"key": key, "text": dst_text[:120]}
                    )

            if fallback_entries and key in fallback_entries:
                src = (
                    fallback_entries[key].get("text_src")
                    or fallback_entries[key].get("text")
                    or fallback_entries[key].get("original_text")
                    or fallback_entries[key].get("text_original")
                    or ""
                )
                if self._normalize_compare_text(dst_text) == self._normalize_compare_text(str(src)):
                    audit["same_as_source"] += 1
                    if len(audit["examples"]["same_as_source"]) < 8:
                        audit["examples"]["same_as_source"].append(
                            {
                                "key": key,
                                "src": str(src)[:120],
                                "dst": dst_text[:120],
                            }
                        )
        effective_total = max(
            1,
            int(audit["total_lines"]),
        )
        audit["effective_total_lines"] = effective_total
        total = effective_total
        audit["ptbr_rate"] = round((audit["ptbr_likely"] / total) * 100.0, 2)
        return audit

    def _is_probable_nontext_garbage(self, text: str) -> bool:
        """Detecta linhas que parecem tabela/código e não texto natural."""
        raw = text if isinstance(text, str) else ""
        s = raw.strip()
        if not s:
            return True
        if self._is_charset_table_like_text(s):
            return True
        letters = sum(1 for ch in s if ch.isalpha())
        digits = sum(1 for ch in s if ch.isdigit())
        punct = sum(1 for ch in s if (not ch.isalnum() and not ch.isspace()))
        spaces = sum(1 for ch in s if ch.isspace())
        total = len(s)

        nontext_ratio = (digits + punct) / max(1, total)
        alpha_ratio = letters / max(1, total)
        if letters < 2 and (digits + punct) >= 2:
            return True
        if nontext_ratio >= 0.35 and alpha_ratio < 0.65:
            return True
        # Sequências sem espaço e com alternância letra/símbolo normalmente são lixo de tabela.
        if spaces == 0 and letters >= 4 and punct >= 3:
            if len(re.findall(r"[A-Za-z][^A-Za-z0-9\s]", s)) >= 3:
                return True
        if spaces == 0 and punct >= 4 and digits >= 2:
            return True
        if re.search(r"[A-Z]{8,}", s) and re.search(r"[0-9]{3,}", s):
            return True
        return False

    def _is_charset_table_like_text(self, text: str) -> bool:
        """
        Detecta sequências técnicas de charset/teclado (alfabeto+numérico),
        que não devem ser traduzidas.
        """
        raw = str(text or "")
        s = re.sub(r"\s+", "", raw)
        if not s:
            return False

        low = s.lower()
        # Caso clássico de tabela de digitação em ROM retro.
        if "abcdefghijklmnopqrstuvwxyz" in low and "0123456789" in low:
            return True

        # Sequências quase completas de letras/dígitos indicam tabela técnica.
        letters = [ch.lower() for ch in s if ch.isalpha()]
        digits = [ch for ch in s if ch.isdigit()]
        unique_letters = len(set(letters))
        unique_digits = len(set(digits))
        if len(s) >= 24 and unique_letters >= 18 and unique_digits >= 6:
            return True
        return False

    def _is_llm_refusal_text(self, text: str) -> bool:
        """Detecta respostas inválidas de LLM (recusa/meta-comentário)."""
        low = str(text or "").strip().lower()
        if not low:
            return False
        markers = (
            "nao posso cumprir esse pedido",
            "não posso cumprir esse pedido",
            "nao posso ajudar com esse pedido",
            "não posso ajudar com esse pedido",
            "nao posso ajudar com isso",
            "não posso ajudar com isso",
            "i can't help with that",
            "i cannot help with that",
            "i'm sorry, i can't",
            "as an ai",
        )
        return any(m in low for m in markers)

    def _forced_source_translation_override(self, src_text: str) -> str:
        """
        Correções determinísticas para frases críticas conhecidas do script.
        Mantém compatibilidade de layout (frases curtas e sem caracteres exóticos).
        """
        if not isinstance(src_text, str):
            return ""
        norm = re.sub(r"\s+", " ", src_text).strip().lower()
        if not norm:
            return ""

        exact: Dict[str, str] = {
            "therworld,in a time to come.": "em outro mundo.",
            "in a time to come.": "em um tempo por vir.",
            "p options:": "Opções:",
            "options:": "Opções:",
            "journey onward": "continuar",
            "initiate new game": "novo jogo",
            "return to the view": "voltar à visão",
            "art thou male or female?": "és masc. ou fem.?",
            "male": "MASC.",
            "female": "FEM.",
            "afterlife?...": "além da vida?...",
            "hill. still clutching the": "colina. ainda segurando",
            "hite stone": "PEDRA BRAN",
        }
        direct = exact.get(norm)
        if direct:
            return direct

        if "world and time" in norm and "name" in norm:
            return "qual teu nome?"
        if "in this world and time?" in norm:
            return "qual teu nome?"
        if "male or female" in norm:
            return "és masc. ou fem.?"
        if "she says" in norm and "consider this" in norm:
            return 'ela diz: "considere isto!"'
        if "another world" in norm and "time to come" in norm:
            return "em outro mundo, em um tempo por vir."
        return ""

    def _is_probable_code_or_name(self, text: str) -> bool:
        """Detecta tokens curtos/códigos/nomes próprios que não exigem tradução."""
        raw = text if isinstance(text, str) else ""
        if not raw.strip():
            return True
        t = raw.strip()
        if re.fullmatch(r"[A-Z0-9\.\:_'\-]{2,12}", t):
            return True

        words = [w for w in self._word_re.findall(t)]
        if not words:
            return True
        if len(words) == 1:
            w = words[0]
            wl = w.lower()
            # Não tratar como "código/nome" se houver tradução direta no glossário.
            mapped = self._en_to_pt_words.get(wl)
            if mapped and mapped != wl:
                return False
            if len(w) <= 4:
                return True
            if w.isupper() and len(w) <= 8:
                return True
            if w[:1].isupper() and w[1:].islower():
                if wl not in self._en_hint_words and wl not in self._pt_hint_words:
                    return True
        return False

    def _is_actionable_untranslated_same_source(self, src_text: str, dst_text: str) -> bool:
        """Retorna True apenas quando 'igual ao source' é provável falha real de tradução."""
        src = src_text if isinstance(src_text, str) else ""
        dst = dst_text if isinstance(dst_text, str) else ""
        if self._normalize_compare_text(src) != self._normalize_compare_text(dst):
            return False
        if self._is_non_standalone_prefix_fragment(src, {"PREFIX_FRAGMENT"}):
            return False

        words = [w.lower() for w in self._word_re.findall(src)]
        if not words:
            return False
        # Item técnico do U4/SMS (ex.: "HITE STONE") pode aparecer truncado
        # no source e não representa falha de tradução textual.
        src_upper = str(src or "").strip().upper()
        if src_upper.endswith(" STONE") and len(words) <= 2:
            return False
        has_direct_glossary_hit = any(
            (w in self._en_to_pt_words) and (self._en_to_pt_words.get(w, "") != w)
            for w in words
        )
        if self._is_probable_code_or_name(src) and not has_direct_glossary_hit:
            return False
        letters = sum(1 for ch in src if ch.isalpha())
        ratio = letters / max(1, len(src))
        if ratio < 0.50:
            return False
        if has_direct_glossary_hit:
            return True

        info = self._classify_language_line(src)
        if info.get("is_english"):
            return True

        en_hits = sum(1 for w in words if w in self._en_hint_words)
        pt_hits = sum(1 for w in words if w in self._pt_hint_words)
        if en_hits >= 1 and pt_hits == 0 and len("".join(words)) >= 4:
            return True
        return False

    def _looks_phrase_like_text(self, text: str) -> bool:
        """Detecta frase exibível (não token/código curto)."""
        raw = text if isinstance(text, str) else ""
        compact = re.sub(r"\s+", " ", raw).strip()
        if " " not in compact:
            return False
        words = [w for w in self._word_re.findall(compact)]
        letters = sum(1 for ch in compact if ch.isalpha())
        return len(words) >= 2 and letters >= 4

    def _contains_english_stopwords(self, text: str) -> bool:
        """Marca provável inglês residual para limpeza automática."""
        raw = text if isinstance(text, str) else ""
        words = [w.lower() for w in self._word_re.findall(raw.lower())]
        if not words:
            return False
        hits = sum(1 for w in words if w in self._en_stopwords_gate)
        return hits >= 1

    def _extract_source_text(self, meta: Optional[Dict[str, Any]]) -> str:
        if not isinstance(meta, dict):
            return ""
        src = (
            meta.get("text_src")
            or meta.get("text")
            or meta.get("original_text")
            or meta.get("text_original")
            or ""
        )
        return src if isinstance(src, str) else ""

    def _normalized_review_flags(self, meta: Optional[Dict[str, Any]]) -> List[str]:
        """Normaliza flags de revisão para UPPER_CASE."""
        if not isinstance(meta, dict):
            return []
        raw = meta.get("review_flags")
        if isinstance(raw, list):
            return [str(x).strip().upper() for x in raw if str(x).strip()]
        if isinstance(raw, str) and raw.strip():
            return [part.strip().upper() for part in raw.split(",") if part.strip()]
        return []

    def _fragment_autotranslate_pt(self, text: str) -> str:
        """
        Fallback determinístico para fragmentos em inglês.
        Não usa IA online; apenas glossário/regras locais.
        """
        if not isinstance(text, str):
            return ""
        out = self._normalize_translation_for_reinsertion(text)
        out = re.sub(r"\s+", " ", out).strip()
        if not out:
            return out

        # Frases longas em inglês (especialmente com placeholders) degradam
        # quando passam por substituição palavra-a-palavra. Tenta API primeiro.
        src_info = self._classify_language_line(text)
        if bool(src_info.get("is_english", False)) and int(src_info.get("word_count", 0)) >= 4:
            api_first = self._translate_with_api_preserving_placeholders(text)
            if not api_first:
                api_first = self._translate_with_api_fallback(text)
            if api_first:
                api_norm = self._normalize_translation_for_reinsertion(api_first)
                if api_norm:
                    return api_norm

        phrase_norm = re.sub(r"\s+", " ", str(out)).strip().lower()
        phrase_overrides = {
            "art thou male or female ?": "és masc. ou fem.?",
            "art thou male or female?": "és masc. ou fem.?",
            "es tu masc ou femin ?": "és masc. ou fem.?",
            "es tu masc ou femin?": "és masc. ou fem.?",
            "es homem ou mulher ?": "és masc. ou fem.?",
            "es homem ou mulher?": "és masc. ou fem.?",
            "by what name shalt thou be known in this world and time ?": (
                "qual será teu nome?"
            ),
            "by what name shalt thou be known in this world and time?": (
                "qual será teu nome?"
            ),
            "qual nome teras neste mundo agora ?": "qual será teu nome?",
            "qual nome teras neste mundo agora?": "qual será teu nome?",
            "\" in this world and time?": "qual teu nome?",
            "in this world and time?": "qual teu nome?",
            "in another world, in a time to come.": "em outro mundo, em um tempo por vir.",
            "therworld,in a time to come.": "em outro mundo.",
            "p options:": "Opções:",
            "journey onward": "continuar",
            "initiate new game": "novo jogo",
            "return to the view": "voltar à visão",
            "afterlife?...": "além da vida?...",
            "she says \"consider this!\"": "ela diz \"considere isto!\"",
            "she says 'consider this!'": "ela diz 'considere isto!'",
            "it is difficult to look at the": "e difícil olhar para o",
            "the portal hangs there for a": "o portal paira ali por um",
            "with trembling hands you": "com mãos trêmulas você",
            "the script on the cover of the": "o texto na capa do",
            "you pick up an amulet shaped": "você pega um amuleto em forma",
            "tinto the depths!": "Nas profundezas!",
            "yet this afternoon walk in the": "Mas esta caminhada da tarde",
            "high-pitched cascading sound": "som agudo em cascata",
            "sound seems to be": "o som parece ser",
            "imploding vacuum, it sinks": "vacuo implodindo afunda",
            "stones surrounds the": "pedras cercam o",
            "kyle the younger": "Kyle o Jovem",
            "hill. still clutching the": "colina. ainda segurando",
            "the music continues to pull": "a musica continua a puxar",
            "you enter to find an old gypsy": "voce entra e ve velha cigana",
            "best adventure rations, 25 for only": "racoes de aventura, 25 apenas",
            "ya see i gots:": "Viu? Eu tenho:",
            "hauntingly familiar, lute-like": "familiar e assombrosa, alaude",
            "the honest inn": "Pousada Leal",
            "ap the book. behold, the": "abra livro. veja o",
            "em the woods. the": "na floresta. o",
            "but only a very small room with 1 bed: worse yet, it is haunted! if you do wish to stay it costs 5gp.": (
                "mas so um quarto pequeno com 1 cama: pior, e assombrado! se quiser ficar custa 5gp."
            ),
            "herbs and spice": "Ervas e Tempero",
            "the bloody pub": "O Pub Sangrento",
            "won't pay, eh. ya scum, be gone fore ey call the guards!": (
                "Nao vai pagar? Entao suma antes que eu chame os guardas!"
            ),
        }
        if phrase_norm in phrase_overrides:
            return phrase_overrides.get(phrase_norm, out)
        out = self._apply_word_glossary(out)
        replacements = [
            (r"\byou pick up\b", "voce pega"),
            (r"\bpick up\b", "pega"),
            (r"\byou\b", "voce"),
            (r"\byour\b", "seu"),
            (r"\bmy\b", "meu"),
            (r"\bour\b", "nosso"),
            (r"\bwe\b", "nos"),
            (r"\bthey\b", "eles"),
            (r"\bthem\b", "eles"),
            (r"\bhe\b", "ele"),
            (r"\bshe\b", "ela"),
            (r"\bit\b", "isso"),
            (r"\bhere\b", "aqui"),
            (r"\bthere\b", "ali"),
            (r"\bfind\b", "encontra"),
            (r"\bfound\b", "encontrou"),
            (r"\bsaving\b", "salvando"),
            (r"\battacked\b", "atacado"),
            (r"\bambushed\b", "emboscado"),
            (r"\bvictory\b", "vitoria"),
            (r"\blevel\b", "nivel"),
            (r"\bfloor\b", "andar"),
            (r"\bspell\b", "magia"),
            (r"\bspells\b", "magias"),
            (r"\bmagic\b", "magia"),
            (r"\bmagical\b", "magico"),
            (r"\bitem\b", "item"),
            (r"\bitems\b", "itens"),
            (r"\bhow\b", "como"),
            (r"\bmany\b", "muitos"),
            (r"\bwhat\b", "o que"),
            (r"\bwho\b", "quem"),
            (r"\bwhere\b", "onde"),
            (r"\bwhen\b", "quando"),
            (r"\bwhy\b", "por que"),
            (r"\bthy\b", "teu"),
            (r"\bthyself\b", "a ti mesmo"),
            (r"\bthou\b", "tu"),
            (r"\bthee\b", "te"),
            (r"\bthine\b", "teu"),
            (r"\bhast\b", "tens"),
            (r"\bhath\b", "tem"),
            (r"\bshalt\b", "deves"),
            (r"\bart\b", "es"),
            (r"\bsworn\b", "jurado"),
            (r"\buphold\b", "defender"),
            (r"\blord\b", "lorde"),
            (r"\bparticipates?\b", "participa"),
            (r"\bbattle\b", "batalha"),
            (r"\bally\b", "aliado"),
            (r"\bdeserter\b", "desertor"),
            (r"\bsurrounded\b", "cercado"),
            (r"\benemies\b", "inimigos"),
            (r"\bunwitnessed\b", "sem testemunhas"),
            (r"\bslain\b", "matou"),
            (r"\bcrossroads\b", "encruzilhada"),
            (r"\blife\b", "vida"),
            (r"\bchoose\b", "escolhe"),
            (r"\bshepherd\b", "pastor"),
            (r"\bsimplicity\b", "simplicidade"),
            (r"\bpeace\b", "paz"),
            (r"\balthough\b", "embora"),
            (r"\bteacher\b", "mestre"),
            (r"\bmusic\b", "musica"),
            (r"\bskillful\b", "habilidoso"),
            (r"\bwrestler\b", "lutador"),
            (r"\basked\b", "chamado"),
            (r"\bfight\b", "lutar"),
            (r"\baccept\b", "aceita"),
            (r"\binvitation\b", "convite"),
            (r"\bbounty\b", "recompensa"),
            (r"\bhunter\b", "cacador"),
            (r"\breturn\b", "retornar"),
            (r"\balleged\b", "suposto"),
            (r"\bmurderer\b", "assassino"),
            (r"\bcapture\b", "captura"),
            (r"\bbelievest\b", "acreditas"),
            (r"\binnocent\b", "inocente"),
            (r"\bsacrifice\b", "sacrifica"),
            (r"\bsizable\b", "grande"),
            (r"\bbonus\b", "bonus"),
            (r"\bbelief\b", "fe"),
            (r"\boath\b", "juramento"),
            (r"\bpromised\b", "prometeste"),
            (r"\bis\b", "e"),
            (r"\bare\b", "sao"),
            (r"\bwas\b", "era"),
            (r"\bwere\b", "eram"),
            (r"\bhave\b", "tem"),
            (r"\bhas\b", "tem"),
            (r"\bhad\b", "tinha"),
            (r"\bwill\b", "vai"),
            (r"\bcan\b", "pode"),
            (r"\bcannot\b", "nao pode"),
            (r"\bdont\b", "nao"),
            (r"\bdo not\b", "nao"),
            (r"\bnot\b", "nao"),
            (r"\bfrom\b", "de"),
            (r"\bwith\b", "com"),
            (r"\bwithout\b", "sem"),
            (r"\bfor\b", "para"),
            (r"\bthe\b", "o"),
            (r"\binto\b", "em"),
            (r"\bto\b", "para"),
            (r"\bof\b", "de"),
            (r"\bin\b", "em"),
            (r"\bon\b", "em"),
            (r"\bonly\b", "apenas"),
            (r"\bdark\b", "escuro"),
            (r"\bwounded\b", "ferido"),
            (r"\blost\b", "perdido"),
            (r"\bspirit\b", "espirito"),
            (r"\bvoid\b", "vazio"),
            (r"\bmotion\b", "movimento"),
            (r"\bhear\b", "ouve"),
            (r"\bsays\b", "diz"),
            (r"\bbook\b", "livro"),
            (r"\bwoods\b", "floresta"),
            (r"\bbehold\b", "veja"),
            (r"\binviting\b", "acolhedor"),
        ]
        for pattern, repl in replacements:
            out = re.sub(pattern, repl, out, flags=re.IGNORECASE)
        # Contrações básicas para reduzir mistura EN/PT residual.
        contractions = [
            (r"\bem o\b", "no"),
            (r"\bem a\b", "na"),
            (r"\bde o\b", "do"),
            (r"\bde a\b", "da"),
            (r"\ba o\b", "ao"),
            (r"\bpara o\b", "pro"),
            (r"\bpara a\b", "pra"),
        ]
        for pattern, repl in contractions:
            out = re.sub(pattern, repl, out, flags=re.IGNORECASE)
        fragment_map = {
            "critical": "critico",
            "wounded": "ferido",
            "truth": "verdade",
            "courage": "coragem",
            "compassionate": "compassivo",
            "valiant": "valoroso",
            "humble": "humilde",
            "lightning": "raio",
            "rocks": "pedras",
            "bridge": "ponte",
            "chest": "bau",
            "holds": "contem",
            "invaded": "invadido",
            "weapon": "arma",
            "armour": "armadura",
            "armor": "armadura",
            "magic": "magia",
            "white": "branco",
            "here": "aqui",
            "says": "diz",
            "spirit": "espirito",
            "void": "vazio",
            "sworn": "jurado",
            "uphold": "defender",
            "lord": "lorde",
            "battle": "batalha",
            "ally": "aliado",
            "deserter": "desertor",
            "surrounded": "cercado",
            "enemies": "inimigos",
            "slain": "matou",
            "crossroads": "encruzilhada",
            "choose": "escolhe",
            "teacher": "mestre",
            "music": "musica",
            "skillful": "habilidoso",
            "wrestler": "lutador",
            "invitation": "convite",
            "bounty": "recompensa",
            "hunter": "cacador",
            "alleged": "suposto",
            "murderer": "assassino",
            "innocent": "inocente",
            "sacrifice": "sacrifica",
            "promised": "prometeste",
        }

        def _frag_repl(match: re.Match) -> str:
            token = match.group(0)
            lw = token.lower()
            mapped = fragment_map.get(lw)
            if not mapped and len(lw) >= 4:
                hits = [
                    (len(k) - len(lw), k, v)
                    for k, v in fragment_map.items()
                    if len(k) > len(lw) and k.endswith(lw)
                ]
                if hits:
                    hits.sort(key=lambda it: (it[0], len(it[1])))
                    mapped = hits[0][2]
            if not mapped:
                return token
            if token.isupper():
                return mapped.upper()
            if token[:1].isupper():
                return mapped[:1].upper() + mapped[1:]
            return mapped

        out = re.sub(r"[A-Za-z']+", _frag_repl, out)
        out = re.sub(r"\s+", " ", out).strip()
        out_info = self._classify_language_line(out)
        src_words = [w.lower() for w in self._word_re.findall(str(text or "").lower())]
        dst_words = [w.lower() for w in self._word_re.findall(str(out or "").lower())]
        shared_words = 0
        if src_words and dst_words:
            src_pool = set(src_words)
            shared_words = sum(1 for w in dst_words if w in src_pool)
        shared_ratio = (
            float(shared_words) / float(max(1, len(src_words)))
            if src_words
            else 0.0
        )
        needs_api = (
            self._contains_english_stopwords(out)
            or (
                bool(out_info.get("is_english", False))
                and not bool(out_info.get("is_ptbr", False))
            )
            or (
                self._normalize_compare_text(out) == self._normalize_compare_text(text)
                and bool(src_info.get("is_english", False))
            )
            or (
                bool(src_info.get("is_english", False))
                and len(src_words) >= 4
                and shared_ratio >= 0.35
            )
        )
        if needs_api:
            api_text = self._translate_with_api_preserving_placeholders(text)
            if not api_text:
                api_text = self._translate_with_api_fallback(text)
            if api_text:
                api_tokens = self._extract_tokens(text)
                if not api_tokens or self._tokens_present(api_text, api_tokens):
                    normalized_api = self._normalize_translation_for_reinsertion(api_text)
                    if normalized_api and (
                        self._normalize_compare_text(normalized_api)
                        != self._normalize_compare_text(out)
                    ):
                        out = normalized_api
                        self._api_fallback_rewrites += 1
        return out

    def _can_autounblock_review_fragment(
        self,
        meta: Optional[Dict[str, Any]],
        src_text: str,
        dst_text: str,
    ) -> Tuple[bool, str, str]:
        """
        Decide se item needs_review/reinsertion_safe=false pode ser aplicado com segurança.
        Retorna (allowed, final_text, reason_tag).
        """
        if not isinstance(meta, dict):
            return False, dst_text, "meta_missing"

        if os.environ.get("NEUROROM_AUTOUNBLOCK_PREFIX_REVIEW", "1") != "1":
            return False, dst_text, "autounblock_disabled"

        flags = set(self._normalized_review_flags(meta))
        if not flags:
            return False, dst_text, "no_review_flags"

        src_norm = self._normalize_compare_text(src_text)
        dst_norm = self._normalize_compare_text(dst_text)
        final_text = dst_text

        # Caso especial: scripts com placeholders {B:XX}. Mantém os tokens e
        # permite autounblock apenas quando há mudança real e texto plausível.
        if self._is_placeholder_review_candidate(meta, src_text=src_text):
            src_tokens = self._extract_tokens(src_text)
            if src_norm == dst_norm:
                auto_pt = self._fragment_autotranslate_pt(src_text)
                if self._normalize_compare_text(auto_pt) != src_norm and auto_pt.strip():
                    final_text = auto_pt
                else:
                    return False, dst_text, "unchanged_placeholder"
            if src_tokens and not self._tokens_present(final_text, src_tokens):
                return False, dst_text, "placeholder_token_missing"
            src_probe = re.sub(r"\{B:[0-9A-Fa-f]{2}\}", " ", str(src_text or ""))
            dst_probe = re.sub(r"\{B:[0-9A-Fa-f]{2}\}", " ", str(final_text or ""))
            if self._is_probable_nontext_garbage(src_probe) or self._is_probable_nontext_garbage(dst_probe):
                return False, dst_text, "nontext_placeholder"
            return True, final_text, "placeholder_autounblock"

        allowed_flags = {
            "PREFIX_FRAGMENT",
            "OVERLAP_FRAGMENT",
            "OVERLAP_DISCARDED",
            "TOO_SHORT_TEXT",
        }
        blocked_flags = {
            "ROUNDTRIP_FAIL",
            "HAS_UNKNOWN_BYTES",
            "HAS_BYTE_PLACEHOLDER",
            "TOO_SHORT_FRAGMENT",
            "NOT_PLAUSIBLE_TEXT_SMS",
        }
        if flags & blocked_flags:
            return False, dst_text, "critical_review_flag"
        if not flags.issubset(allowed_flags):
            return False, dst_text, "unsupported_review_flag"

        if meta.get("audit_roundtrip_ok") is False:
            return False, dst_text, "roundtrip_fail"
        unknown = self._parse_optional_int_value(meta.get("unknown_bytes_count"))
        if unknown is not None and int(unknown) > 0:
            return False, dst_text, "unknown_bytes"

        if src_norm == dst_norm:
            auto_pt = self._fragment_autotranslate_pt(src_text)
            if self._normalize_compare_text(auto_pt) != src_norm and auto_pt.strip():
                final_text = auto_pt
            else:
                return False, dst_text, "unchanged_fragment"

        if self._is_probable_nontext_garbage(src_text) or self._is_probable_nontext_garbage(final_text):
            return False, dst_text, "nontext_fragment"

        return True, final_text, "fragment_autounblock"

    def _is_non_standalone_prefix_fragment(
        self,
        text: str,
        review_flags: Optional[set] = None,
    ) -> bool:
        """
        Detecta shards de PREFIX_FRAGMENT (sufixos/partes compartilhadas) que
        geralmente nao aparecem sozinhos em tela.
        """
        flags = review_flags or set()
        if "PREFIX_FRAGMENT" not in flags:
            return False
        compact = re.sub(r"\s+", " ", str(text or "")).strip()
        if not compact:
            return True
        starts_suspicious = bool(
            compact[:1] and (compact[0].islower() or compact[0] in ".,;:!?')-_/")
        )
        short_single_token = (" " not in compact) and len(compact) <= 18
        tiny_fragment = (" " not in compact) and len(compact) <= 4
        return bool(starts_suspicious or short_single_token or tiny_fragment)

    def _detect_hidden_ctrl_prefix_fragment(
        self,
        rom_data: bytearray,
        entry: MapEntry,
        source_text: str = "",
        max_chars: int = 64,
    ) -> Optional[Dict[str, Any]]:
        """
        Detecta fragmentos ASCII_CTRL cujo texto inicia no meio de uma frase
        já presente imediatamente antes do offset.
        """
        if not isinstance(rom_data, (bytes, bytearray)):
            return None
        if str(entry.encoding or "").lower() != "ascii_ctrl_prefixed":
            return None
        off = int(entry.offset)
        if off < 2 or off >= len(rom_data):
            return None

        slots: List[int] = []
        chars: List[str] = []
        idx = off - 2
        while idx >= 0 and len(slots) < max(1, int(max_chars)):
            ch = int(rom_data[idx])
            ctrl = int(rom_data[idx + 1])
            if ch in (0x00, 0xFF):
                break
            ctrl_ok = (0x01 <= ctrl <= 0x1F)
            # Algumas tabelas usam o terminador (0x00/0xFF) no último par da
            # frase anterior; nesse caso ainda aceitamos o primeiro caractere.
            if not ctrl_ok and (ctrl in (0x00, 0xFF)) and (not slots):
                ctrl_ok = True
            if 32 <= ch <= 126 and ctrl_ok:
                slots.append(int(idx))
                chars.append(chr(ch))
                idx -= 2
                continue
            break
        if not slots:
            return None
        slots.reverse()
        chars.reverse()
        prefix_text = "".join(chars)
        src = str(source_text or "")
        src_first = src[:1]
        has_letters = any(ch.isalpha() for ch in prefix_text)
        suspicious_fragment = bool(
            has_letters
            and len(prefix_text.strip()) >= 3
            and (
                (src_first and src_first.islower())
                or (src_first in "\"'([{")
                or (src_first and (not src_first.isalnum()))
            )
        )
        return {
            "prefix_text": prefix_text,
            "slots": slots,
            "suspicious_fragment": suspicious_fragment,
        }

    def _suggest_ptbr_hidden_prefix_fix(
        self,
        prefix_text: str,
        translated_text: str,
    ) -> Optional[Tuple[str, str]]:
        """
        Ajuste específico para ULTIMA4 SMS (intro): evita "In ano" + tradução
        fragmentada e reconstrói a frase curta em PT-BR.
        """
        prefix_norm = self._normalize_compare_text(prefix_text)
        if "bywhatnameshaltthoubeknown" in prefix_norm:
            # Consolida a pergunta em uma linha curta PT-BR.
            return ("Qual teu nome?", " ")
        if prefix_norm != "inano":
            return None
        lang_info = self._classify_language_line(str(translated_text or ""))
        if not bool(lang_info.get("is_ptbr")):
            return None
        txt_norm = self._normalize_compare_text(translated_text)
        if "mundo" in txt_norm:
            # Divide propositalmente "outro" no limite do fragmento para
            # recompor "Em outro mundo." sem depender de espaço inicial.
            return ("Em ou", "tro mundo.")
        return ("Em um", " ")

    def _apply_hidden_prefix_patch_slots(
        self,
        rom_data: bytearray,
        patch: Optional[Dict[str, Any]],
    ) -> None:
        """Aplica patch de caracteres em slots ASCII intercalados por control bytes."""
        if not isinstance(rom_data, bytearray):
            return
        if not isinstance(patch, dict):
            return
        slots_raw = patch.get("slots") or []
        text = str(patch.get("text") or "")
        slots: List[int] = []
        for value in slots_raw:
            parsed = self._parse_optional_int_value(value)
            if parsed is None:
                continue
            slots.append(int(parsed))
        if not slots:
            return
        for idx, pos in enumerate(slots):
            if not (0 <= int(pos) < len(rom_data)):
                continue
            ch = text[idx] if idx < len(text) else " "
            code = ord(ch) if isinstance(ch, str) and len(ch) == 1 else 0x20
            if code < 0x20 or code > 0x7E:
                code = 0x20
            rom_data[int(pos)] = int(code)

    def _is_non_plausible_text_meta(self, meta: Optional[Dict[str, Any]]) -> bool:
        """Detecta entradas técnicas que não representam texto natural traduzível."""
        if not isinstance(meta, dict) or not meta:
            return False
        reason = str(meta.get("reason_code") or meta.get("blocked_reason") or "").strip().upper()
        return reason == "NOT_PLAUSIBLE_TEXT_SMS"

    def _is_placeholder_review_candidate(
        self,
        meta: Optional[Dict[str, Any]],
        src_text: str = "",
    ) -> bool:
        """
        Detecta entradas de script com placeholders ``{B:XX}`` que podem ser
        promovidas para autounblock controlado.
        """
        if not isinstance(meta, dict) or not meta:
            return False
        flags = set(self._normalized_review_flags(meta))
        if not flags:
            return False
        allowed = {
            "HAS_BYTE_PLACEHOLDER",
            "HAS_UNKNOWN_BYTES",
            "NOT_PLAUSIBLE_TEXT_SMS",
            "OVERLAP_DISCARDED",
        }
        if not flags.issubset(allowed):
            return False
        probe = str(src_text or self._extract_source_text(meta) or "")
        return "{B:" in probe

    def _has_overlap_placeholder_sibling(
        self,
        key: str,
        entry: Optional[MapEntry],
        fallback_entries: Optional[Dict[str, Dict[str, Any]]],
    ) -> bool:
        """
        Detecta fragmento curto sobreposto a um bloco maior com placeholders
        no mesmo offset. Evita gravar fragmento parcial (caso clássico do
        Ultima IV: chave curta + chave narrativa longa no mesmo endereço).
        """
        if not isinstance(entry, MapEntry):
            return False
        if not isinstance(fallback_entries, dict):
            return False

        cur_key = str(key)
        cur_off = int(entry.offset)
        cur_len = max(0, int(entry.max_len))
        if cur_len <= 0:
            return False

        for other_key, other_meta in fallback_entries.items():
            if str(other_key) == cur_key:
                continue
            if not isinstance(other_meta, dict):
                continue
            off_val = self._parse_optional_int_value(
                other_meta.get("offset", other_meta.get("rom_offset"))
            )
            if off_val is None or int(off_val) != cur_off:
                continue

            src_other = self._extract_source_text(other_meta)
            if "{B:" not in str(src_other or ""):
                continue

            other_len = self._parse_optional_int_value(
                other_meta.get(
                    "max_len",
                    other_meta.get("max_len_bytes", other_meta.get("raw_len")),
                )
            )
            if other_len is None:
                other_len = len(str(src_other or ""))
            if int(other_len) >= int(cur_len) + 8:
                return True
        return False

    def _read_ascii_text_from_rom(self, rom_data: bytes, entry: MapEntry) -> Tuple[str, bool]:
        """Lê texto ASCII atual da ROM para auditoria de divergência."""
        if not isinstance(rom_data, (bytes, bytearray)):
            return "", False
        rom_len = len(rom_data)
        off = int(entry.offset)
        max_len = max(0, int(entry.max_len))
        if off < 0 or off >= rom_len or max_len <= 0:
            return "", False

        payload_end = min(rom_len, off + max_len)
        payload = bytes(rom_data[off:payload_end])
        term = entry.terminator
        term_present = True

        if term is not None:
            scan_end = min(rom_len, off + max_len + 1)
            scan = bytes(rom_data[off:scan_end])
            term_byte = int(term) & 0xFF
            pos = scan.find(bytes([term_byte]))
            if pos >= 0:
                payload = scan[:pos]
                term_present = True
            else:
                term_present = False

        chars: List[str] = []
        for b in payload:
            if 32 <= b <= 126:
                chars.append(chr(b))
            elif b in (0x09, 0x0A, 0x0D):
                chars.append(" ")
            else:
                chars.append(" ")
        text = re.sub(r"\s+", " ", "".join(chars)).strip()
        return text, term_present

    def _empty_issue_index(self) -> Dict[str, Any]:
        categories = list(self.DELTA_ISSUE_CATEGORIES)
        return {
            "categories": categories,
            "counts": {cat: 0 for cat in categories},
            "examples": {cat: [] for cat in categories},
            "keys_by_category": {cat: [] for cat in categories},
            "total_unique_keys": 0,
            "checked_items": 0,
        }

    def _build_incremental_issue_index(
        self,
        translated: Dict[str, str],
        fallback_entries: Optional[Dict[str, Dict[str, Any]]] = None,
        rom_bytes: Optional[bytes] = None,
        restrict_keys: Optional[set] = None,
        runtime_entry_overrides: Optional[Dict[str, Dict[str, int]]] = None,
    ) -> Dict[str, Any]:
        """Classifica problemas de reinserção para geração/validação de delta."""
        index = self._empty_issue_index()
        if not translated:
            return index

        categories = list(self.DELTA_ISSUE_CATEGORIES)
        counts = index["counts"]
        examples = index["examples"]
        keys_by_category = index["keys_by_category"]
        seen_by_category = {cat: set() for cat in categories}
        unique_keys: set = set()

        def _add_issue(cat: str, key: str, sample: Optional[Dict[str, Any]] = None):
            if cat not in seen_by_category:
                return
            if key in seen_by_category[cat]:
                return
            seen_by_category[cat].add(key)
            keys_by_category[cat].append(key)
            counts[cat] = int(counts.get(cat, 0)) + 1
            unique_keys.add(key)
            if sample and len(examples[cat]) < 8:
                clean = {k: v for k, v in sample.items() if v is not None}
                clean.setdefault("key", key)
                examples[cat].append(clean)

        def _sort_key(raw_key: str):
            parsed = self._parse_optional_int_value(raw_key)
            if parsed is not None:
                return (0, int(parsed), "")
            return (1, 0, str(raw_key))

        ordered_keys = sorted([str(k) for k in translated.keys()], key=_sort_key)
        for key in ordered_keys:
            if restrict_keys is not None and key not in restrict_keys:
                continue

            index["checked_items"] = int(index.get("checked_items", 0)) + 1
            dst_text = translated.get(key, "")
            if not isinstance(dst_text, str):
                dst_text = str(dst_text)
            if not dst_text.strip():
                continue

            meta = fallback_entries.get(key) if fallback_entries else {}
            src_text = self._extract_source_text(meta)
            review_flags_upper = set(self._normalized_review_flags(meta))
            non_standalone_prefix = self._is_non_standalone_prefix_fragment(
                src_text,
                review_flags=review_flags_upper,
            )
            if self._is_non_plausible_text_meta(meta):
                continue

            if src_text:
                src_tokens = self._extract_tokens(src_text)
                if src_tokens and not self._tokens_present(dst_text, src_tokens):
                    _add_issue(
                        "placeholder_fail",
                        key,
                        {
                            "src": src_text[:120],
                            "dst": dst_text[:120],
                            "missing_tokens": [tok for tok in src_tokens if tok not in dst_text][:8],
                        },
                    )

                if (not non_standalone_prefix) and self._is_actionable_untranslated_same_source(src_text, dst_text):
                    _add_issue(
                        "unchanged_equal_src",
                        key,
                        {"src": src_text[:120], "dst": dst_text[:120]},
                    )

            lang_info = self._classify_language_line(dst_text)
            if (
                (not non_standalone_prefix)
                and (
                (not lang_info.get("is_ptbr", False))
                and (not lang_info.get("is_noise", False))
                and int(lang_info.get("word_count", 0)) >= 2
                and (not self._is_probable_nontext_garbage(dst_text))
                and (not self._is_probable_nontext_garbage(src_text))
                )
            ):
                _add_issue(
                    "suspicious_non_pt",
                    key,
                    {"text": dst_text[:120], "pt_score": lang_info.get("pt_score"), "en_score": lang_info.get("en_score")},
                )

            if rom_bytes is None:
                continue

            entry = self.mapping.get(key)
            if entry is None and isinstance(meta, dict) and meta:
                entry = self._mapentry_from_jsonl(key, meta)
            if entry is None:
                continue
            runtime_off = None
            runtime_max_len = None
            if isinstance(runtime_entry_overrides, dict):
                override = runtime_entry_overrides.get(key)
                if isinstance(override, dict):
                    runtime_off = self._parse_optional_int_value(override.get("offset"))
                    runtime_max_len = self._parse_optional_int_value(override.get("max_len"))
            if runtime_off is not None and runtime_off >= 0:
                entry = MapEntry(
                    key=str(entry.key),
                    offset=int(runtime_off),
                    max_len=(
                        int(runtime_max_len)
                        if runtime_max_len is not None and int(runtime_max_len) > 0
                        else int(entry.max_len)
                    ),
                    raw_len=int(entry.raw_len) if self._parse_optional_int_value(entry.raw_len) else None,
                    category=str(entry.category),
                    has_pointer=bool(entry.has_pointer),
                    pointer_offsets=list(entry.pointer_offsets or []),
                    pointer_refs=list(entry.pointer_refs or []),
                    terminator=(int(entry.terminator) if entry.terminator is not None else None),
                    encoding=str(entry.encoding),
                    reinsertion_safe=bool(entry.reinsertion_safe),
                    blocked_reason=entry.blocked_reason,
                )
            if str(entry.encoding).lower() in ("tile", "tilemap"):
                continue

            self._resolve_entry_terminator(
                entry,
                meta if isinstance(meta, dict) else None,
            )
            rom_text, term_present = self._read_ascii_text_from_rom(rom_bytes, entry)
            sanitized_dst, _ = self._sanitize_ascii_text_with_fallback(dst_text)
            mismatch_detected = (
                self._normalize_compare_text(rom_text) != self._normalize_compare_text(sanitized_dst)
            )
            ui_ascii_ctrl_entry = False
            if isinstance(meta, dict):
                context_tag = str(meta.get("context_tag") or "").strip().lower()
                source_hint = str(meta.get("source") or "").strip().upper()
                ui_item_hint = bool(meta.get("ui_item", False))
                if (
                    str(entry.encoding).strip().lower() == "ascii_ctrl_prefixed"
                    and (
                        context_tag.startswith("ui_pointer_")
                        or source_hint.startswith("UI_POINTER_")
                        or ui_item_hint
                    )
                ):
                    ui_ascii_ctrl_entry = True
            ui_prefixed_match = False
            if mismatch_detected:
                context_tag = str(meta.get("context_tag") or "").strip().lower() if isinstance(meta, dict) else ""
                src_low = str(src_text or "").strip().lower()
                rom_wo_prefix = re.sub(r"^[Pp]\s+", "", str(rom_text or ""), count=1)
                prefix_matches = (
                    self._normalize_compare_text(rom_wo_prefix)
                    == self._normalize_compare_text(sanitized_dst)
                )
                if prefix_matches and (
                    context_tag.startswith("ui_pointer_")
                    or src_low.startswith("p options")
                    or src_low.startswith("options")
                    or self._normalize_compare_text(sanitized_dst).startswith("opcoes")
                ):
                    ui_prefixed_match = True
            if (
                (not non_standalone_prefix)
                and sanitized_dst
                and mismatch_detected
                and (not ui_prefixed_match)
                and (not ui_ascii_ctrl_entry)
            ):
                _add_issue(
                    "rom_vs_translated_mismatch",
                    key,
                    {
                        "offset": f"0x{int(entry.offset):06X}",
                        "rom_text": rom_text[:120],
                        "dst": sanitized_dst[:120],
                    },
                )

            if entry.terminator is not None and not term_present:
                _add_issue(
                    "terminator_missing",
                    key,
                    {
                        "offset": f"0x{int(entry.offset):06X}",
                        "expected_terminator": int(entry.terminator),
                    },
                )

        for cat in categories:
            keys_by_category[cat] = sorted(keys_by_category.get(cat, []), key=_sort_key)
        index["total_unique_keys"] = len(unique_keys)
        return index

    # Layout base de diálogo (fallback) para consoles de cartucho.
    SMS_DEFAULT_DIALOG_WIDTH = 28
    SMS_DEFAULT_DIALOG_LINES = 4
    SMS_MAX_DIALOG_LINES_HARD = 8

    def _infer_wrap_width(self, orig_text: str, max_len: int) -> Optional[int]:
        """Infere largura de word-wrap a partir do texto original.

        Se o texto original não tiver newlines mas for longo o bastante para
        precisar de wrap (> SMS_DEFAULT_DIALOG_WIDTH chars), retorna a largura
        padrão de diálogo SMS.
        """
        defaults = self._get_dialog_defaults()
        default_width = int(defaults.get("width", self.SMS_DEFAULT_DIALOG_WIDTH))

        plat_key = str(self._target_platform or "SMS").upper()
        env_raw = (
            os.environ.get(f"NEUROROM_{plat_key}_BOX_COLS", "").strip()
            or os.environ.get("NEUROROM_DIALOG_BOX_COLS", "").strip()
            or os.environ.get("NEUROROM_SMS_BOX_COLS", "").strip()
        )
        if env_raw:
            try:
                env_cols = int(env_raw)
                if env_cols > 0:
                    return max(6, min(env_cols, 64))
            except Exception:
                pass
        if not isinstance(orig_text, str):
            return None
        if "\n" in orig_text:
            lines = [ln.strip() for ln in orig_text.splitlines() if ln.strip()]
            if not lines:
                return None
            width = max(len(ln) for ln in lines)
            if width <= 0:
                return None
            if max_len > 0:
                width = min(width, max_len)
            width = max(6, min(width, 32))
            return width
        # Texto sem newlines: se for longo, assume largura padrão da plataforma.
        if len(orig_text) > default_width:
            return default_width
        return None

    def _wrap_text_for_dialog(self, text: str, width: int) -> str:
        """Aplica wrap sem quebrar palavras."""
        if not isinstance(text, str):
            return ""
        clean = re.sub(r"[ \t]+", " ", text).strip()
        if not clean or width < 4:
            return clean
        wrapped = textwrap.wrap(
            clean,
            width=width,
            break_long_words=False,
            break_on_hyphens=False,
        )
        return "\n".join(wrapped) if wrapped else clean

    def _infer_wrap_max_lines(self, orig_text: str) -> int:
        """Infere limite de linhas para diálogo com possibilidade de override."""
        defaults = self._get_dialog_defaults()
        default_lines = int(defaults.get("lines", self.SMS_DEFAULT_DIALOG_LINES))
        max_hard = int(defaults.get("max_lines_hard", self.SMS_MAX_DIALOG_LINES_HARD))

        plat_key = str(self._target_platform or "SMS").upper()
        env_raw = (
            os.environ.get(f"NEUROROM_{plat_key}_BOX_LINES", "").strip()
            or os.environ.get("NEUROROM_DIALOG_BOX_LINES", "").strip()
            or os.environ.get("NEUROROM_SMS_BOX_LINES", "").strip()
        )
        if env_raw:
            try:
                env_lines = int(env_raw)
                if env_lines > 0:
                    return max(1, min(env_lines, max_hard))
            except Exception:
                pass
        if not isinstance(orig_text, str) or not orig_text.strip():
            return default_lines
        src_lines = [ln for ln in orig_text.replace("\r", "").split("\n") if ln.strip()]
        if not src_lines:
            return default_lines
        # PT costuma expandir: adiciona +1 linha de folga, com teto seguro.
        inferred = len(src_lines) + 1
        return max(2, min(inferred, max_hard))

    def _infer_page_break_token(self, orig_text: str) -> Optional[str]:
        """
        Detecta token de quebra de página conhecido.
        Só habilita automaticamente se já existir no texto fonte ou em override explícito.
        """
        forced = str(os.environ.get("NEUROROM_SMS_PAGE_TOKEN", "") or "").strip()
        if forced:
            return forced
        if not isinstance(orig_text, str) or not orig_text:
            return None
        for tok in ("{B:01}", "{B:0C}", "{B:FE}", "{B:FF}"):
            if tok in orig_text:
                return tok
        return None

    def _tokenize_wrap_preserving_placeholders(self, text: str) -> List[Dict[str, str]]:
        """
        Tokeniza mantendo placeholders/tokens como unidades indivisíveis:
        - WORD: palavra normal
        - TOKEN: {..} [..] <..>
        - SPACE: espaço normalizado
        - NL: quebra manual '\n'
        """
        if not isinstance(text, str) or not text:
            return []
        out: List[Dict[str, str]] = []
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if ch == "\n":
                out.append({"type": "NL", "value": "\n"})
                i += 1
                continue
            if ch in "\r\t ":
                while i < n and text[i] in "\r\t ":
                    i += 1
                out.append({"type": "SPACE", "value": " "})
                continue
            if ch in "{[<":
                match = self._token_re.match(text, i)
                if match:
                    token = match.group(0)
                    out.append({"type": "TOKEN", "value": token})
                    i = match.end()
                    continue
            j = i
            while j < n:
                cj = text[j]
                if cj == "\n" or cj in "\r\t ":
                    break
                if cj in "{[<":
                    look = self._token_re.match(text, j)
                    if look:
                        break
                j += 1
            out.append({"type": "WORD", "value": text[i:j]})
            i = j
        return out

    def _wrap_visible_len(self, token_type: str, value: str) -> int:
        """Mede largura visual para wrap monoespaçado, preservando tokens de controle."""
        if token_type == "TOKEN":
            if self._byte_placeholder_re.fullmatch(value or ""):
                return 0
            if (value.startswith("<") and value.endswith(">")) or (
                value.startswith("[") and value.endswith("]")
            ):
                return 0
            # Placeholders textuais ({NAME}) contam como curto para evitar estouro inesperado.
            if value.startswith("{") and value.endswith("}"):
                return 4
        return len(value or "")

    def _count_layout_lines(
        self, text: str, page_break_token: Optional[str] = None
    ) -> Tuple[int, int]:
        """Retorna (linhas_totais, maior_linhas_por_página)."""
        if not isinstance(text, str) or not text:
            return 0, 0
        if page_break_token and page_break_token in text:
            pages = text.split(page_break_token)
        else:
            pages = [text]
        total = 0
        peak = 0
        for page in pages:
            line_count = len(page.splitlines()) if page else 0
            total += line_count
            peak = max(peak, line_count)
        return total, peak

    def _wrap_text_box_aware(
        self,
        text: str,
        width: int,
        max_lines: int = 0,
        page_break_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Wrap monoespaçado preservando placeholders e quebras manuais.
        Se estourar max_lines, pagina automaticamente quando page_break_token estiver disponível.
        """
        clean = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if not clean:
            return {
                "text": "",
                "lines": [],
                "line_count": 0,
                "line_count_peak_per_page": 0,
                "fits": True,
                "used_pagination": False,
            }
        if width < 4:
            width = 4

        tokens = self._tokenize_wrap_preserving_placeholders(clean)
        lines: List[str] = []
        current_parts: List[str] = []
        current_len = 0
        pending_space = False

        def flush_line() -> None:
            nonlocal current_parts, current_len, pending_space
            line = "".join(current_parts).rstrip()
            lines.append(line)
            current_parts = []
            current_len = 0
            pending_space = False

        for tok in tokens:
            tok_type = tok.get("type", "")
            value = tok.get("value", "")
            if tok_type == "NL":
                flush_line()
                continue
            if tok_type == "SPACE":
                if current_parts:
                    pending_space = True
                continue

            token_len = self._wrap_visible_len(tok_type, value)
            spacer_len = 1 if pending_space and current_parts else 0
            if current_parts and (current_len + spacer_len + token_len) <= width:
                if spacer_len:
                    current_parts.append(" ")
                    current_len += 1
                current_parts.append(value)
                current_len += token_len
                pending_space = False
                continue

            if not current_parts:
                # Palavra grande sem espaço: só quebra palavra normal; TOKEN fica inteiro.
                if tok_type == "WORD" and token_len > width:
                    remaining = value
                    while len(remaining) > width:
                        piece = remaining[: max(1, width - 1)] + "-"
                        lines.append(piece)
                        remaining = remaining[max(1, width - 1) :]
                    current_parts = [remaining]
                    current_len = len(remaining)
                    pending_space = False
                    continue
                current_parts = [value]
                current_len = token_len
                pending_space = False
                continue

            flush_line()
            if tok_type == "WORD" and token_len > width:
                remaining = value
                while len(remaining) > width:
                    piece = remaining[: max(1, width - 1)] + "-"
                    lines.append(piece)
                    remaining = remaining[max(1, width - 1) :]
                current_parts = [remaining]
                current_len = len(remaining)
            else:
                current_parts = [value]
                current_len = token_len
            pending_space = False

        if current_parts:
            flush_line()

        # Remove linhas vazias nas bordas.
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()

        used_pagination = False
        output_lines = list(lines)
        if max_lines > 0 and len(output_lines) > max_lines and page_break_token:
            used_pagination = True
            pages: List[str] = []
            for i in range(0, len(output_lines), max_lines):
                page = "\n".join(output_lines[i : i + max_lines]).strip()
                pages.append(page)
            joined = page_break_token.join(pages)
            total_lines, peak_lines = self._count_layout_lines(joined, page_break_token=page_break_token)
            return {
                "text": joined,
                "lines": output_lines,
                "line_count": int(total_lines),
                "line_count_peak_per_page": int(peak_lines),
                "fits": bool(peak_lines <= max_lines),
                "used_pagination": True,
            }

        joined_plain = "\n".join(output_lines).strip()
        total_lines, peak_lines = self._count_layout_lines(joined_plain)
        fits = bool(max_lines <= 0 or peak_lines <= max_lines)
        return {
            "text": joined_plain,
            "lines": output_lines,
            "line_count": int(total_lines),
            "line_count_peak_per_page": int(peak_lines),
            "fits": fits,
            "used_pagination": used_pagination,
        }

    def _apply_word_glossary(self, text: str) -> str:
        """Converte palavras comuns em EN para PT-BR."""
        if not text:
            return ""
        text = self._normalize_unicode_nfc(text)

        def repl(match: re.Match) -> str:
            word = match.group(0)
            mapped = self._en_to_pt_words.get(word.lower())
            if not mapped:
                return word
            if word.isupper():
                return mapped.upper()
            if word[0].isupper():
                return mapped.capitalize()
            return mapped

        return re.sub(r"[A-Za-zÀ-ÿ']+", repl, text)

    def _normalize_short_key(self, token: str) -> str:
        """Normaliza token para lookup em short-style map."""
        if not isinstance(token, str):
            return ""
        folded = unicodedata.normalize("NFKD", token)
        folded = "".join(ch for ch in folded if unicodedata.category(ch) != "Mn")
        folded = re.sub(r"[^A-Za-z0-9]+", "", folded).lower()
        return folded

    def _apply_short_style_sanitization(self, text: str) -> str:
        """Aplica abreviações curtas naturais antes de bloquear por overflow."""
        if not text:
            return ""

        def repl(match: re.Match) -> str:
            token = match.group(0)
            key = self._normalize_short_key(token)
            mapped = self.SHORT_STYLE_MAP.get(key)
            if not mapped:
                mapped = self.PT_ABBREVIATIONS.get(token.lower())
            if not mapped:
                return token
            if token.isupper():
                return mapped.upper()
            if token[:1].isupper():
                return mapped[:1].upper() + mapped[1:]
            return mapped

        return re.sub(r"[A-Za-zÀ-ÿ']+", repl, text)

    def _apply_pt_abbreviations(self, text: str) -> str:
        """Abrevia termos comuns em PT-BR para caber no limite."""
        if not text:
            return ""

        def repl(match: re.Match) -> str:
            token = match.group(0)
            mapped = self.PT_ABBREVIATIONS.get(token.lower())
            if not mapped:
                return token
            return mapped.upper() if token.isupper() else mapped

        return re.sub(r"[A-Za-zÀ-ÿ']+", repl, text)

    def _drop_low_priority_words(self, text: str) -> str:
        """Remove palavras pouco informativas para ganhar espaço."""
        if not text:
            return ""
        words = text.split()
        if len(words) <= 2:
            return text
        kept: List[str] = []
        for idx, word in enumerate(words):
            cleaned = re.sub(r"[^A-Za-zÀ-ÿ0-9]+", "", word).lower()
            if idx == 0 or cleaned not in self.PT_DROP_WORDS:
                kept.append(word)
        return " ".join(kept) if kept else text

    def _compact_word(self, word: str, max_chars: int) -> str:
        """Compacta palavra preservando legibilidade mínima."""
        if not word:
            return word
        if len(word) <= max_chars:
            return word
        m = re.match(r"^([^A-Za-zÀ-ÿ]*)([A-Za-zÀ-ÿ]+)([^A-Za-zÀ-ÿ]*)$", word)
        if not m:
            return word[:max_chars]
        prefix, core, suffix = m.groups()
        if len(core) <= max_chars:
            return word[:max_chars]
        first = core[0]
        tail = [c for c in core[1:] if c.lower() not in "aeiou"]
        if not tail:
            tail = list(core[1:])
        packed = (first + "".join(tail))[: max(1, max_chars - len(prefix) - len(suffix))]
        out = f"{prefix}{packed}{suffix}"
        return out[:max_chars]

    def _initials_variant(self, text: str, max_len: int) -> Optional[str]:
        """Gera variante ultra-curta com iniciais."""
        if max_len <= 0:
            return None
        words = [w for w in self._word_re.findall(text) if w]
        if not words:
            return text[:max_len] if text else None
        initials = "".join(w[0] for w in words if w)
        if len(initials) >= 2:
            return initials[:max_len].upper()
        return words[0][:max_len]

    def _fit_ascii_reformulation(
        self,
        text: str,
        orig_text: str,
        payload_limit: int,
        term: bytes,
        tokens: List[str],
        allow_compact: bool = True,
        allow_hard_trim: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Tenta variações de texto até caber no limite de bytes."""
        if payload_limit <= 0:
            return None
        base_text = text if isinstance(text, str) else ""
        wrap_width = self._infer_wrap_width(orig_text, payload_limit)
        max_lines = self._infer_wrap_max_lines(orig_text)
        page_break_token = self._infer_page_break_token(orig_text)
        candidates: List[Dict[str, Any]] = []

        def add_candidate(
            strategy: str,
            candidate_text: str,
            preserve_newlines: bool,
            reformulated: bool,
            hard_trim: bool = False,
        ):
            if isinstance(candidate_text, str) and candidate_text.strip():
                candidates.append(
                    {
                        "strategy": strategy,
                        "text": candidate_text,
                        "preserve_newlines": preserve_newlines,
                        "reformulated": reformulated,
                        "hard_trim": hard_trim,
                    }
                )

        def add_wrapped_variant(
            strategy: str,
            candidate_text: str,
            reformulated: bool,
        ) -> None:
            if not isinstance(candidate_text, str) or not candidate_text.strip():
                return
            target_width = wrap_width
            default_width = int(self._get_dialog_defaults().get("width", self.SMS_DEFAULT_DIALOG_WIDTH))
            if not target_width and len(candidate_text) > default_width and " " in candidate_text:
                target_width = default_width
            if not target_width or " " not in candidate_text:
                return
            layout = self._wrap_text_box_aware(
                candidate_text,
                width=int(target_width),
                max_lines=int(max_lines),
                page_break_token=page_break_token,
            )
            wrapped_text = str(layout.get("text", "") or "").strip()
            if not wrapped_text:
                return
            # Só inclui candidato com layout válido por página/caixa.
            if not bool(layout.get("fits", True)):
                return
            add_candidate(strategy, wrapped_text, True, reformulated)

        add_candidate("DIRECT", base_text, False, False)
        add_wrapped_variant("WRAP", base_text, True)

        glossary = self._apply_word_glossary(base_text)
        if glossary != base_text:
            add_candidate("GLOSSARY", glossary, False, True)
            add_wrapped_variant("WRAP_GLOSSARY", glossary, True)

        short_style = self._apply_short_style_sanitization(glossary)
        if short_style and short_style != glossary:
            add_candidate("SHORT_STYLE", short_style, False, True)
            add_wrapped_variant("WRAP_SHORT_STYLE", short_style, True)

        if allow_compact:
            compact_seed = short_style if short_style else glossary
            abbr = self._apply_pt_abbreviations(compact_seed)
            if abbr != compact_seed:
                add_candidate("ABBREV", abbr, False, True)
                add_wrapped_variant("WRAP_ABBREV", abbr, True)
            dropped = self._drop_low_priority_words(abbr)
            if dropped != abbr:
                add_candidate("DROP", dropped, False, True)
                add_wrapped_variant("WRAP_DROP", dropped, True)
            compact = " ".join(self._compact_word(w, 8) for w in dropped.split())
            if compact and compact != dropped:
                add_candidate("COMPACT", compact, False, True)
                add_wrapped_variant("WRAP_COMPACT", compact, True)
            initials = self._initials_variant(dropped or abbr or glossary, payload_limit)
            # Evita siglas artificiais em frases normais (ex.: "VECAF").
            if initials and payload_limit <= 10:
                add_candidate("INITIALS", initials, False, True)

        if allow_hard_trim:
            short = self._shorten_wordwise(glossary, payload_limit)
            if short:
                add_candidate("SHORT_TRIM", short, False, True, hard_trim=True)
                add_wrapped_variant("WRAP_SHORT_TRIM", short, True)

        seen: set = set()
        total_space = payload_limit + len(term)
        for cand in candidates:
            sanitized, fallback_cnt = self._sanitize_ascii_text_with_fallback(
                cand["text"],
                preserve_newlines=bool(cand["preserve_newlines"]),
                preserve_diacritics=True,
            )
            if cand["preserve_newlines"]:
                sanitized = "\n".join(
                    part.strip() for part in sanitized.splitlines() if part.strip()
                )
            else:
                sanitized = re.sub(r"\s+", " ", sanitized).strip()
            if not sanitized:
                continue
            if tokens and not self._tokens_present(sanitized, tokens):
                continue

            if max_lines > 0:
                _, peak_lines = self._count_layout_lines(
                    sanitized, page_break_token=page_break_token
                )
                if peak_lines > max_lines:
                    continue

            sig = (cand["strategy"], sanitized)
            if sig in seen:
                continue
            seen.add(sig)

            encoded, fb_extra, sanitized_log = self._encode_ascii_with_byte_placeholders(
                sanitized,
                preserve_newlines=bool(cand["preserve_newlines"]),
            )
            encoded_with_term = encoded + term
            if len(encoded_with_term) <= total_space:
                return {
                    "encoded_with_term": encoded_with_term,
                    "sanitized": sanitized_log,
                    "strategy": cand["strategy"],
                    "reformulated": bool(cand["reformulated"]),
                    "hard_trim": bool(cand["hard_trim"]),
                    "fallback_chars": int(fallback_cnt) + int(fb_extra),
                }
        return None

    def _normalize_translation_for_reinsertion(self, text: str) -> str:
        """Limpa artefatos de tradução e força vocabulário-base em PT-BR."""
        if not isinstance(text, str):
            return ""
        cleaned = self._normalize_unicode_nfc(text).strip()
        if not cleaned:
            return ""

        apply_custom_first = self._coerce_bool(
            self._translation_runtime_policy.get("apply_custom_dict_first"), True
        )
        if apply_custom_first:
            cleaned, _ = self._apply_custom_dictionary(cleaned)

        # Remove comentários explicativos em inglês gerados por LLM.
        def _parenthetical_filter(match: re.Match) -> str:
            content = match.group(1).strip()
            info = self._classify_language_line(content)
            lowered = content.lower()
            if info["is_english"] or any(
                token in lowered
                for token in (
                    "the rest of your sentence",
                    "if you want",
                    "or simply",
                    "note that",
                    "masculine",
                    "feminine",
                )
            ):
                return ""
            return match.group(0)

        cleaned = re.sub(r"\(([^()]*)\)", _parenthetical_filter, cleaned)
        cleaned = self._apply_word_glossary(cleaned)
        if not apply_custom_first:
            cleaned, _ = self._apply_custom_dictionary(cleaned)

        # Em opções bilíngues do tipo "PT / explicação EN", mantém lado PT.
        if "/" in cleaned:
            parts = [p.strip() for p in cleaned.split("/") if p.strip()]
            if len(parts) >= 2:
                right = parts[1].lower()
                right_info = self._classify_language_line(parts[1])
                if right_info["is_english"] or any(
                    token in right for token in ("mascul", "femin", "or ", "if ")
                ):
                    cleaned = parts[0]

        # Corrige artefatos de duplicação comuns em respostas de LLM ("sShe", etc).
        cleaned = re.sub(r"\bs+she\b", "she", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bs+says\b", "says", cleaned, flags=re.IGNORECASE)

        cleaned = self._restore_common_ptbr_diacritics(cleaned)
        cleaned = self._normalize_unicode_nfc(cleaned)
        # Normaliza espaçamento: múltiplos espaços → 1, remove espaço antes de pontuação
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        # Corrige quebra indevida de abreviações curtas (ex.: "f em." -> "fem.").
        cleaned = re.sub(r"\bf\s+em\.", "fem.", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bm\s+asc\.", "masc.", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bf\s+emin\.", "femin.", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+([.,!?;:)])", r"\1", cleaned)
        cleaned = re.sub(r"([(])\s+", r"\1", cleaned)
        return cleaned

    def _restore_common_ptbr_diacritics(self, text: str) -> str:
        """Restaura diacríticos frequentes de PT-BR após tradução/sanitização."""
        if not isinstance(text, str) or not text:
            return ""

        replacements = {
            "nao": "não",
            "sao": "são",
            "estao": "estão",
            "entao": "então",
            "voce": "você",
            "voces": "vocês",
            "maos": "mãos",
            "tremulas": "trêmulas",
            "ha": "há",
            "ja": "já",
            "ate": "até",
            "tambem": "também",
            "alem": "além",
            "dificil": "difícil",
            "possivel": "possível",
            "avanco": "avanço",
            "musica": "música",
            "vitoria": "vitória",
            "justica": "justiça",
            "sacrificio": "sacrifício",
            "compaixao": "compaixão",
            "teras": "terás",
            "direcao": "direção",
            "direcoes": "direções",
            "opcao": "opção",
            "opcoes": "opções",
        }

        def _repl(match: re.Match) -> str:
            word = match.group(0)
            fixed = replacements.get(word.lower())
            if not fixed:
                return word
            if word.isupper():
                return fixed.upper()
            if word[:1].isupper():
                return fixed.capitalize()
            return fixed

        return re.sub(r"\b[A-Za-zÀ-ÿ]+\b", _repl, text)

    def _coerce_ptbr_line(self, dst_text: str, src_text: str = "") -> str:
        """Pós-processa linha para PT-BR quando modo estrito está habilitado."""
        base = self._normalize_translation_for_reinsertion(dst_text)
        if not base:
            return base
        base_info = self._classify_language_line(base)
        if base_info.get("is_ptbr") and not base_info.get("is_english"):
            return base

        src = src_text if isinstance(src_text, str) else ""
        src_tokens = self._extract_tokens(src)

        candidates: List[str] = [base]
        gloss_dst = self._apply_word_glossary(base)
        if gloss_dst and gloss_dst not in candidates:
            candidates.append(gloss_dst)
        if src.strip():
            gloss_src = self._apply_word_glossary(src)
            if gloss_src and gloss_src not in candidates:
                candidates.append(gloss_src)

        best_text = base
        best_tuple = (
            int(base_info.get("is_ptbr", False)),
            int(base_info.get("pt_score", 0)) - int(base_info.get("en_score", 0)),
            -int(base_info.get("is_english", False)),
        )

        for cand in candidates:
            norm = self._normalize_translation_for_reinsertion(cand)
            if not norm:
                continue
            if src_tokens and not self._tokens_present(norm, src_tokens):
                continue
            info = self._classify_language_line(norm)
            score_tuple = (
                int(info.get("is_ptbr", False)),
                int(info.get("pt_score", 0)) - int(info.get("en_score", 0)),
                -int(info.get("is_english", False)),
            )
            if score_tuple > best_tuple:
                best_tuple = score_tuple
                best_text = norm

        return best_text

    def _extract_tokens(self, text: str) -> List[str]:
        if not text:
            return []
        tokens = [m.group(0) for m in self._token_re.finditer(text)]
        return tokens

    def _tokens_present(self, text: str, tokens: List[str]) -> bool:
        if not tokens:
            return True
        for token in tokens:
            if token not in text:
                return False
        return True

    def _tilemap_roundtrip_ok(self, text: str, tbl) -> bool:
        if not text or not tbl:
            return True
        reverse_map = getattr(tbl, "reverse_map", {}) or {}
        multi_map = getattr(tbl, "multi_byte_map", {}) or {}
        char_map = getattr(tbl, "char_map", {}) or {}
        for ch in text:
            seq = reverse_map.get(ch)
            if not seq:
                return False
            decoded = None
            if seq in multi_map:
                decoded = multi_map.get(seq)
            elif len(seq) == 1 and seq[0] in char_map:
                decoded = char_map.get(seq[0])
            if decoded != ch:
                return False
        return True

    def _compute_diff_ranges(self, before: bytes, after: bytes) -> List[Dict[str, Any]]:
        """Gera ranges contínuos de diferenças entre ROMs."""
        diffs: List[Dict[str, Any]] = []
        if len(before) != len(after):
            min_len = min(len(before), len(after))
            if min_len > 0:
                before = before[:min_len]
                after = after[:min_len]
            extra_start = min_len
            extra_end = max(len(before), len(after))
            if extra_end > extra_start:
                diffs.append(
                    {"start": extra_start, "end": extra_end, "size": extra_end - extra_start}
                )
        start = None
        for i, (b1, b2) in enumerate(zip(before, after)):
            if b1 != b2:
                if start is None:
                    start = i
            else:
                if start is not None:
                    diffs.append({"start": start, "end": i, "size": i - start})
                    start = None
        if start is not None:
            diffs.append({"start": start, "end": len(before), "size": len(before) - start})
        return diffs

    def _range_is_allowed(self, start: int, end: int, allowed: List[Tuple[int, int]]) -> bool:
        """Verifica se [start, end) está coberto pela união dos ranges permitidos."""
        if not allowed:
            return False
        # Ordena e mescla ranges para cobrir adjacências
        sorted_ranges = sorted(allowed)
        merged: List[Tuple[int, int]] = [sorted_ranges[0]]
        for a_start, a_end in sorted_ranges[1:]:
            prev_start, prev_end = merged[-1]
            if a_start <= prev_end:
                merged[-1] = (prev_start, max(prev_end, a_end))
            else:
                merged.append((a_start, a_end))
        for a_start, a_end in merged:
            if start >= a_start and end <= a_end:
                return True
        return False

    def _parse_range_bound(self, value: Any) -> Optional[int]:
        """Converte limite de range (int/hex string) para inteiro."""
        if value is None:
            return None
        if isinstance(value, int):
            return int(value)
        txt = str(value).strip()
        if not txt:
            return None
        try:
            return int(txt, 16) if txt.lower().startswith("0x") else int(txt)
        except Exception:
            return None

    def _parse_ranges_payload(
        self,
        payload: Any,
        rom_size: int,
    ) -> List[Tuple[int, int]]:
        """Extrai ranges [start,end) de payload JSON flexível."""
        ranges: List[Tuple[int, int]] = []
        items: List[Any] = []
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            for key in ("editable_ranges", "allowed_ranges", "ranges", "diff_ranges"):
                cand = payload.get(key)
                if isinstance(cand, list):
                    items = cand
                    break
        for row in items:
            if not isinstance(row, dict):
                continue
            start = self._parse_range_bound(
                row.get("start", row.get("start_hex", row.get("offset")))
            )
            end = self._parse_range_bound(row.get("end", row.get("end_hex")))
            if start is None:
                continue
            if end is None:
                size = self._parse_range_bound(row.get("size", row.get("length")))
                if size is not None and int(size) > 0:
                    end = int(start) + int(size)
            if end is None:
                continue
            start_i = max(0, min(int(start), int(rom_size)))
            end_i = max(0, min(int(end), int(rom_size)))
            if end_i > start_i:
                ranges.append((start_i, end_i))
        return ranges

    def _load_external_allowed_ranges(
        self,
        mapping_path: Optional[Path],
        rom_path: Path,
        crc_tag: str,
        rom_size: int,
    ) -> Tuple[List[Tuple[int, int]], Optional[str]]:
        """
        Carrega ranges extras de arquivo editável.
        Formatos aceitos:
        - lista direta [{start,end}, ...]
        - objeto com editable_ranges/allowed_ranges/ranges/diff_ranges.
        """
        candidates: List[Path] = []
        if mapping_path is not None:
            candidates.extend(
                [
                    mapping_path.parent / f"{crc_tag}_editable_ranges.json",
                    mapping_path.parent / f"{crc_tag}_diff_ranges.json",
                    mapping_path.parent / "editable_ranges.json",
                ]
            )
        rom_dir = rom_path.parent
        candidates.extend(
            [
                rom_dir / crc_tag / f"{crc_tag}_editable_ranges.json",
                rom_dir / crc_tag / f"{crc_tag}_diff_ranges.json",
                rom_dir / crc_tag / "3_reinsercao" / f"{crc_tag}_editable_ranges.json",
                rom_dir / crc_tag / "3_reinsercao" / f"{crc_tag}_diff_ranges.json",
                rom_dir / "out" / f"{crc_tag}_editable_ranges.json",
            ]
        )
        seen: set = set()
        uniq: List[Path] = []
        for cand in candidates:
            try:
                rc = cand.resolve()
            except Exception:
                rc = cand
            if rc in seen:
                continue
            seen.add(rc)
            uniq.append(cand)

        for path in uniq:
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            ranges = self._parse_ranges_payload(payload, rom_size=rom_size)
            if ranges:
                return ranges, str(path)
        return [], None

    def _merge_ranges_with_gap(
        self,
        ranges: List[Tuple[int, int]],
        merge_gap: int = 0,
    ) -> List[Tuple[int, int]]:
        """Mescla ranges contíguos/próximos para reduzir fragmentação."""
        if not ranges:
            return []
        ordered = sorted((int(s), int(e)) for s, e in ranges if int(e) > int(s))
        merged: List[Tuple[int, int]] = [ordered[0]]
        gap = max(0, int(merge_gap))
        for s, e in ordered[1:]:
            ps, pe = merged[-1]
            if s <= pe + gap:
                merged[-1] = (ps, max(pe, e))
            else:
                merged.append((s, e))
        return merged

    def _build_auto_diff_ranges_from_mapping(
        self,
        rom_size: int,
        margin_start: int,
        margin_end: int,
        merge_gap: int,
    ) -> List[Tuple[int, int]]:
        """
        Gera ranges editáveis automaticamente a partir do mapping de reinserção.
        Inclui blocos de texto e ponteiros com margem de segurança configurável.
        """
        ranges: List[Tuple[int, int]] = []
        m_start = max(0, int(margin_start))
        m_end = max(0, int(margin_end))
        max_size = max(1, int(rom_size))
        for entry in self.mapping.values():
            try:
                base_off = int(entry.offset)
            except Exception:
                continue
            slot_size = int(self._resolve_entry_slot_total_len(entry, None))
            if slot_size <= 0:
                slot_size = 1
            start = max(0, base_off - m_start)
            end = min(max_size, base_off + slot_size + m_end)
            if end > start:
                ranges.append((start, end))
            for ref in entry.pointer_refs or []:
                try:
                    ptr_off = int(ref.get("ptr_offset", -1))
                    ptr_size = int(ref.get("ptr_size", 2))
                except Exception:
                    continue
                if ptr_off < 0:
                    continue
                if ptr_size <= 0:
                    ptr_size = 2
                p_start = max(0, ptr_off)
                p_end = min(max_size, ptr_off + ptr_size)
                if p_end > p_start:
                    ranges.append((p_start, p_end))
            for ptr_off in entry.pointer_offsets or []:
                try:
                    po = int(ptr_off)
                except Exception:
                    continue
                p_start = max(0, po)
                p_end = min(max_size, po + 2)
                if p_end > p_start:
                    ranges.append((p_start, p_end))
        return self._merge_ranges_with_gap(ranges, merge_gap=merge_gap)

    def _candidate_auto_diff_ranges_paths(
        self,
        mapping_path: Optional[Path],
        rom_path: Path,
        crc_tag: str,
    ) -> List[Path]:
        """Lista destinos candidatos para salvar ranges auto-gerados."""
        candidates: List[Path] = []
        if mapping_path is not None:
            base = mapping_path.parent
            candidates.extend(
                [
                    base / f"{crc_tag}_editable_ranges.json",
                    base / f"{crc_tag}_diff_ranges.json",
                ]
            )
            # Caso mapping esteja em 1_extracao/2_traducao/3_reinsercao/_interno
            if base.name in {"1_extracao", "2_traducao", "3_reinsercao", "_interno"}:
                crc_dir = base.parent
                candidates.extend(
                    [
                        crc_dir / "3_reinsercao" / f"{crc_tag}_editable_ranges.json",
                        crc_dir / "3_reinsercao" / f"{crc_tag}_diff_ranges.json",
                        crc_dir / "out" / f"{crc_tag}_editable_ranges.json",
                    ]
                )
        rom_dir = rom_path.parent
        candidates.extend(
            [
                rom_dir / crc_tag / "3_reinsercao" / f"{crc_tag}_editable_ranges.json",
                rom_dir / crc_tag / f"{crc_tag}_editable_ranges.json",
                rom_dir / crc_tag / f"{crc_tag}_diff_ranges.json",
                rom_dir / "out" / f"{crc_tag}_editable_ranges.json",
            ]
        )
        uniq: List[Path] = []
        seen: set = set()
        for cand in candidates:
            try:
                rc = cand.resolve()
            except Exception:
                rc = cand
            if rc in seen:
                continue
            seen.add(rc)
            uniq.append(cand)
        return uniq

    def _auto_generate_diff_ranges_from_mapping(
        self,
        mapping_path: Optional[Path],
        rom_path: Path,
        crc_tag: str,
        rom_size: int,
    ) -> Dict[str, Any]:
        """
        Gera automaticamente arquivo de ranges editáveis a partir do mapping.
        Retorna metadados para relatório/log.
        """
        policy = self._translation_runtime_policy if isinstance(self._translation_runtime_policy, dict) else {}
        enabled = self._coerce_bool(policy.get("auto_generate_diff_ranges"), True)
        overwrite = self._coerce_bool(policy.get("auto_generate_diff_ranges_overwrite"), False)
        margin_start = int(self._parse_int_value(policy.get("diff_ranges_margin_start", 2), default=2))
        margin_end = int(self._parse_int_value(policy.get("diff_ranges_margin_end", 16), default=16))
        merge_gap = int(self._parse_int_value(policy.get("diff_ranges_merge_gap", 16), default=16))
        result: Dict[str, Any] = {
            "enabled": bool(enabled),
            "generated": False,
            "ranges_count": 0,
            "written_paths": [],
            "skipped_existing_paths": [],
            "margin_start": max(0, margin_start),
            "margin_end": max(0, margin_end),
            "merge_gap": max(0, merge_gap),
            "overwrite": bool(overwrite),
            "error": "",
        }
        if not enabled:
            return result
        try:
            ranges = self._build_auto_diff_ranges_from_mapping(
                rom_size=rom_size,
                margin_start=margin_start,
                margin_end=margin_end,
                merge_gap=merge_gap,
            )
            result["ranges_count"] = int(len(ranges))
            if not ranges:
                return result
            payload = [
                {
                    "start": f"0x{int(s):X}",
                    "end": f"0x{int(e):X}",
                }
                for s, e in ranges
            ]
            paths = self._candidate_auto_diff_ranges_paths(mapping_path, rom_path, crc_tag)
            for path in paths:
                if path.exists() and not overwrite:
                    result["skipped_existing_paths"].append(str(path))
                    continue
                ensure_parent_dir(path)
                path.write_text(
                    json.dumps(payload, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                result["written_paths"].append(str(path))
            result["generated"] = bool(result["written_paths"])
            return result
        except Exception as exc:
            result["error"] = str(exc)
            return result

    def _shorten_wordwise(self, text: str, max_len: int) -> Optional[str]:
        """Encurta sem cortar palavra; fallback para corte de caractere."""
        if max_len <= 0:
            return None
        text = text.strip()
        if len(text) <= max_len:
            return text
        words = [w for w in text.split(" ") if w]
        if not words:
            return None
        out = ""
        for w in words:
            if not out:
                if len(w) > max_len:
                    # Fallback: corta no limite de caracteres
                    return text[:max_len] if max_len >= 2 else None
                out = w
                continue
            if len(out) + 1 + len(w) <= max_len:
                out = f"{out} {w}"
            else:
                break
        return out if out else None

    def _align(self, value: int, alignment: int) -> int:
        if alignment <= 1:
            return value
        return ((value + alignment - 1) // alignment) * alignment

    def _build_relocation_forbidden_ranges(
        self,
        fallback_entries: Optional[Dict[str, Dict[str, Any]]],
        rom_size: int,
    ) -> List[Tuple[int, int]]:
        """
        Monta regiões que não devem receber alocação de texto realocado.

        A ideia é evitar que o pool de realocação caia sobre slots de texto já
        mapeados, tabelas de ponteiro e ranges gráficos conhecidos.
        """
        max_size = max(1, int(rom_size))
        ranges: List[Tuple[int, int]] = []
        fallback = fallback_entries if isinstance(fallback_entries, dict) else {}

        # Guarda dura para manter cabeçalho/vetores de boot intactos.
        ranges.append((0, min(max_size, 0x0200)))

        for key, entry in self.mapping.items():
            if not isinstance(entry, MapEntry):
                continue
            meta = fallback.get(str(key))
            slot_len = int(self._resolve_entry_slot_total_len(entry, meta if isinstance(meta, dict) else None))
            start = int(entry.offset)
            end = int(entry.offset) + max(1, slot_len)
            if 0 <= start < max_size and end > start:
                ranges.append((start, min(max_size, end)))
            for ref in entry.pointer_refs or []:
                ptr_off = self._parse_optional_int_value(ref.get("ptr_offset"))
                ptr_size = self._parse_optional_int_value(ref.get("ptr_size"))
                if ptr_off is None:
                    continue
                p_size = int(ptr_size) if ptr_size is not None and int(ptr_size) > 0 else 2
                p_start = int(ptr_off)
                p_end = p_start + p_size
                if 0 <= p_start < max_size and p_end > p_start:
                    ranges.append((p_start, min(max_size, p_end)))
            for ptr_off in entry.pointer_offsets or []:
                po = self._parse_optional_int_value(ptr_off)
                if po is None:
                    continue
                p_start = int(po)
                p_end = p_start + 2
                if 0 <= p_start < max_size and p_end > p_start:
                    ranges.append((p_start, min(max_size, p_end)))

        for meta in fallback.values():
            if not isinstance(meta, dict):
                continue
            raw_ranges = meta.get("gfx_ranges", []) or meta.get("graphics_ranges", []) or []
            for rg in raw_ranges:
                try:
                    if isinstance(rg, str) and "-" in rg:
                        a, b = rg.split("-", 1)
                        start = int(a.strip(), 16)
                        end = int(b.strip(), 16)
                    else:
                        start = int(rg.get("start", 0))
                        end = int(rg.get("end", 0))
                    if start < 0:
                        start = 0
                    if end > max_size:
                        end = max_size
                    if end > start:
                        ranges.append((start, end))
                except Exception:
                    continue

        return self._merge_ranges_with_gap(ranges, merge_gap=0)

    def _find_free_space(
        self,
        rom: bytes,
        min_len: int,
        filler_bytes: Tuple[int, ...] = (0xFF, 0x00),
        alignment: int = 1,
        forbidden_ranges: Optional[List[Tuple[int, int]]] = None,
    ) -> Tuple[Optional[int], Optional[int]]:
        """Encontra região contínua de filler_bytes com tamanho mínimo.

        Estratégia:
        1) Prioriza espaço livre no FINAL da ROM (blocos 0xFF/0x00), reduzindo
           risco de colidir com regiões ativas.
        2) Depois busca de trás para frente por runs válidos.
        3) Fallback: busca progressiva clássica.
        """
        if min_len <= 0:
            return None, None
        rom_len = len(rom)
        forbidden = self._merge_ranges_with_gap(
            [
                (
                    max(0, int(s)),
                    min(int(rom_len), int(e)),
                )
                for s, e in (forbidden_ranges or [])
                if int(e) > int(s)
            ],
            merge_gap=0,
        )

        def _fit_candidate_in_run(run_start: int, run_end: int) -> Optional[int]:
            if run_end <= run_start:
                return None
            candidate = self._align(int(run_start), alignment)
            while candidate + min_len <= run_end:
                cand_end = candidate + min_len
                collision = None
                for fs, fe in forbidden:
                    if fe <= candidate:
                        continue
                    if fs >= cand_end:
                        break
                    collision = (fs, fe)
                    break
                if collision is None:
                    return candidate
                candidate = self._align(max(candidate + 1, int(collision[1])), alignment)
            return None

        for fb in filler_bytes:
            # 1) Trailing run no final da ROM.
            j = rom_len - 1
            while j >= 0 and rom[j] == fb:
                j -= 1
            tail_start = j + 1
            tail_len = rom_len - tail_start
            if tail_len >= min_len:
                aligned = _fit_candidate_in_run(tail_start, rom_len)
                if aligned is not None:
                    return aligned, fb

            # 2) Runs em ordem reversa (prioriza offsets mais altos).
            i = rom_len - 1
            while i >= 0:
                if rom[i] != fb:
                    i -= 1
                    continue
                run_end = i + 1
                while i >= 0 and rom[i] == fb:
                    i -= 1
                run_start = i + 1
                run_len = run_end - run_start
                if run_len < min_len:
                    continue
                aligned = _fit_candidate_in_run(run_start, run_end)
                if aligned is not None:
                    return aligned, fb

            # 3) Fallback clássico (frente -> trás).
            run_start = None
            run_len = 0
            for i in range(rom_len):
                if rom[i] == fb:
                    if run_start is None:
                        run_start = i
                        run_len = 1
                    else:
                        run_len += 1
                else:
                    if run_start is not None and run_len >= min_len:
                        aligned = _fit_candidate_in_run(run_start, run_start + run_len)
                        if aligned is not None:
                            return aligned, fb
                    run_start = None
                    run_len = 0
            if run_start is not None and run_len >= min_len:
                aligned = _fit_candidate_in_run(run_start, run_start + run_len)
                if aligned is not None:
                    return aligned, fb
        return None, None

    def _calc_pointer_value(self, new_offset: int, ref: Dict[str, Any]) -> Optional[int]:
        bank_addend = int(ref.get("bank_addend", 0) or 0)
        value = new_offset - bank_addend
        if value < 0:
            return None
        return value

    def _write_pointer_value(
        self, rom: bytearray, ref: Dict[str, Any], value: int
    ) -> bool:
        ptr_offset = int(ref.get("ptr_offset", -1))
        ptr_size = int(ref.get("ptr_size", 2))
        endianness = str(ref.get("endianness", "little")).lower()
        if ptr_offset < 0 or ptr_offset + ptr_size > len(rom):
            return False
        max_val = 1 << (ptr_size * 8)
        if value < 0 or value >= max_val:
            return False
        try:
            data = value.to_bytes(ptr_size, endianness)
        except Exception:
            return False
        rom[ptr_offset : ptr_offset + ptr_size] = data
        return True

    def _refs_are_generic(
        self,
        refs: List[Dict[str, Any]],
        pointer_offsets: List[int],
    ) -> bool:
        """Detecta refs sintéticas (ABSOLUTE + addend 0) que podem ser enriquecidas."""
        if not refs:
            return True
        ptr_set = {self._parse_int_value(x, default=-1) for x in (pointer_offsets or [])}
        for ref in refs:
            mode = str(ref.get("addressing_mode", "ABSOLUTE")).upper()
            addend = self._parse_int_value(ref.get("bank_addend", 0), default=0)
            ptr_off = self._parse_int_value(ref.get("ptr_offset", -1), default=-1)
            ptr_size = self._parse_int_value(ref.get("ptr_size", 2), default=2)
            if ptr_size != 2:
                return False
            if mode not in {"ABSOLUTE", "DIRECT"}:
                return False
            if addend != 0:
                return False
            if ptr_set and ptr_off not in ptr_set:
                return False
        return True

    def _mapentry_from_jsonl(self, key: str, obj: Dict[str, Any]) -> Optional[MapEntry]:
        """Converte entrada JSONL em MapEntry quando o mapping está incompleto."""
        # offset obrigatório
        off = obj.get("offset", obj.get("origin_offset", obj.get("static_offset")))
        if off is None:
            return None
        if isinstance(off, str):
            s = off.strip()
            try:
                off = int(s, 16) if s.lower().startswith("0x") else int(s)
            except ValueError:
                return None

        # max_len obrigatório (usa vários nomes possíveis)
        max_len = (obj.get("max_len") or obj.get("max_len_bytes") or obj.get("max_bytes") or
                   obj.get("max_length"))
        if max_len is None:
            return None
        try:
            max_len = int(max_len)
        except (TypeError, ValueError):
            return None

        # terminador
        term = obj.get("terminator")
        if term is None and obj.get("terminator_hex"):
            try:
                term = int(str(obj.get("terminator_hex")), 16)
            except ValueError:
                term = None

        # ponteiros
        pointer_offsets: List[int] = []
        ptrs = obj.get("pointer_offsets") or []
        for p in ptrs:
            poff = self._parse_int_value(p, default=-1)
            if poff >= 0:
                pointer_offsets.append(int(poff))

        pointer_refs: List[Dict[str, Any]] = []
        ptr_refs = obj.get("pointer_refs") or []
        for ref in ptr_refs:
            poff = self._parse_int_value(ref.get("ptr_offset"), default=-1)
            if poff >= 0:
                pointer_refs.append(
                    {
                        "ptr_offset": int(poff),
                        "ptr_size": self._parse_int_value(ref.get("ptr_size", 2), default=2),
                        "endianness": str(ref.get("endianness", "little")).lower(),
                        "addressing_mode": str(ref.get("addressing_mode", "ABSOLUTE")),
                        "bank_addend": self._parse_int_value(ref.get("bank_addend", 0), default=0),
                    }
                )

        # Se só temos offsets simples, cria refs básicas
        if pointer_offsets and not pointer_refs:
            pointer_refs = [
                {
                    "ptr_offset": int(poff),
                    "ptr_size": 2,
                    "endianness": "little",
                    "addressing_mode": "ABSOLUTE",
                    "bank_addend": 0,
                }
                for poff in pointer_offsets
            ]

        has_pointer = bool(pointer_refs or pointer_offsets or obj.get("has_pointer", False))
        encoding = str(obj.get("encoding", "ascii") or "ascii").lower()
        source_hint = str(obj.get("source", "") or "").upper()
        is_ui_item = bool(obj.get("ui_item", False) or source_hint.startswith("UI_POINTER_"))

        # Segurança: não cria entrada sintética para texto sem ponteiro.
        # Isso evita escrita indevida de scans cegos (ex.: ASCII_BRUTE) fora do mapping.
        if not has_pointer and encoding != "tilemap" and not is_ui_item:
            return None

        term_val = self._parse_optional_int_value(term)
        if term_val is not None:
            term_val = int(term_val) & 0xFF
        raw_len_val = self._parse_optional_int_value(
            obj.get("raw_len", obj.get("max_len_bytes", obj.get("max_length")))
        )
        if raw_len_val is not None and int(raw_len_val) <= 0:
            raw_len_val = None
        return MapEntry(
            key=str(key),
            offset=int(off),
            max_len=int(max_len),
            raw_len=(int(raw_len_val) if raw_len_val is not None else None),
            category=str(obj.get("category", "Unknown")),
            has_pointer=has_pointer,
            pointer_offsets=pointer_offsets,
            pointer_refs=pointer_refs,
            terminator=(int(term_val) if term_val is not None else None),
            encoding=encoding,
            reinsertion_safe=bool(obj.get("reinsertion_safe", True)),
            blocked_reason=(obj.get("blocked_reason") or obj.get("reason_code")),
        )

    # ---------- allocation + repoint ----------

    def _find_free_space_bank0(self, rom: bytearray, size: int, fill: bytes = b"\xFF") -> Optional[int]:
        # procura um buraco de 0xFF na bank0
        hay = bytes(rom[: self.BANK0_LIMIT])
        needle = fill * size
        idx = hay.find(needle)
        return idx if idx != -1 else None

    def _read_u16_le(self, rom: bytearray, off: int) -> int:
        return rom[off] | (rom[off + 1] << 8)

    def _write_u16_le(self, rom: bytearray, off: int, value: int):
        rom[off] = value & 0xFF
        rom[off + 1] = (value >> 8) & 0xFF

    # ---------- apply ----------

    def apply_translation(
        self,
        rom_path: Path,
        translated_path: Path,
        mapping_path: Optional[Path] = None,
        output_rom_path: Optional[Path] = None,
        force_blocked: bool = False,
        translated: Optional[Dict[str, str]] = None,
        fallback_entries: Optional[Dict[str, Dict[str, Any]]] = None,
        strict: bool = False,
        dry_run: bool = False,
        create_backup: bool = True,
        report_path: Optional[Path] = None,
        delta_context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Path, Dict[str, int]]:
        self.set_target_rom(rom_path)

        if mapping_path is None:
            mapping_path = self._guess_mapping_path(translated_path, rom_path)
        if mapping_path is None or not mapping_path.exists():
            raise ReinsertionError("mapping.json não encontrado (o app precisa achar *_mapping.json na mesma pasta).")

        self.load_mapping(mapping_path)
        if translated is None:
            translated = self.load_translated_blocks(translated_path)

        rom_bytes = Path(rom_path).read_bytes()
        rom = bytearray(rom_bytes)
        crc_before, sha_before = compute_checksums(rom_bytes)
        runtime_crc_upper = str(crc_before).upper()
        strict_policy_enabled = self._coerce_bool(
            self._translation_runtime_policy.get("strict_crc_safe_mode"),
            False,
        )
        strict_target_crc32 = str(
            self._translation_runtime_policy.get(
                "strict_crc_safe_mode_target_crc32", "DE9F8517"
            )
            or "DE9F8517"
        ).strip().upper()
        strict_crc_safe_mode = bool(
            strict_policy_enabled
            and strict_target_crc32
            and runtime_crc_upper == strict_target_crc32
        )
        self._game_engineering_text_changes = 0
        game_engineering_info = self._load_game_engineering_profile(runtime_crc_upper)
        compression_policy = game_engineering_info.get("compression", {})
        if isinstance(compression_policy, dict) and bool(
            compression_policy.get("block_reinsertion", False)
        ):
            raise ReinsertionError(
                "Perfil de engenharia por jogo bloqueou a reinserção para esta ROM "
                f"(mode={compression_policy.get('mode')}, notes={compression_policy.get('notes')})."
            )

        stats = {
            "OK": 0,
            "REPOINT": 0,
            "TRUNC": 0,
            "BLOCKED": 0,
            "SKIP": 0,
            "FORCED": 0,
            "REFORM": 0,
            "WRAP": 0,
            "SKIP_NO_MAPPING": 0,
            "SKIP_ID_OVERRIDE_PRIORITY": 0,
            "BLOCKED_UNSAFE": 0,
            "BLOCKED_BANK0": 0,
            "BLOCKED_PTR_MISMATCH": 0,
            "BLOCKED_NO_SPACE": 0,
            "BLOCKED_NO_POINTER": 0,
            "BLOCKED_RELOC_DISABLED": 0,
            "BLOCKED_INVALID": 0,
            "TRUNC_OVERFLOW": 0,
            "PTR_FROM_META": 0,
            "STRICT_PTBR": 0,
            "ID_OVERRIDE": 0,
            "GAME_ENGINEERING_REWRITE": 0,
            "AUTO_UNBLOCK_REVIEW": 0,
            "TILEMAP_BLOCKED_NO_TBL": 0,
            "LAYOUT_ADJUSTED": 0,
            "LAYOUT_SHORT_STYLE": 0,
            "GUARDRAIL_WARN": 0,
            "SAFE_REVERT": 0,
        }

        items_report: List[Dict[str, Any]] = []
        rom_size = len(rom)
        glyph_injection_report: Optional[Dict[str, Any]] = None
        glyph_allowed_ranges: List[Tuple[int, int]] = []
        protected_regions = self.load_protected_regions(runtime_crc_upper, rom_size)
        expected_mutable_ranges = self._collect_expected_mutable_ranges(
            rom_size=int(rom_size),
            fallback_entries=fallback_entries,
        )
        protected_backup, protected_excluded_bytes = self._build_protected_backup(
            rom=rom,
            protected_regions=protected_regions,
            mutable_ranges=expected_mutable_ranges,
        )
        protected_integrity_summary = {
            "enabled": bool(protected_regions),
            "protected_regions_count": int(len(protected_regions)),
            "protected_backup_bytes": int(len(protected_backup)),
            "protected_mutable_ranges_count": int(len(expected_mutable_ranges)),
            "protected_excluded_bytes": int(protected_excluded_bytes),
            "changed_protected_bytes": 0,
            "reverted_blocks": 0,
            "reverted_bytes": 0,
            "remaining_changed_bytes": 0,
            "logs": [],
        }

        # --- Glyph injection (PT-BR accents) ---
        # In STRICT charset policy, detect missing chars and inject font tiles.
        charset_policy = str(
            os.environ.get("NEUROROM_CHARSET_POLICY", "strict") or "strict"
        ).strip().lower()
        glyph_injection_enabled = bool(
            self._coerce_bool(
                self._translation_runtime_policy.get("glyph_injection_enabled"),
                True,
            )
        )
        if strict_crc_safe_mode:
            glyph_injection_enabled = False
        glyph_font = str(
            self._translation_runtime_policy.get("glyph_font", "Verdana.ttf") or "Verdana.ttf"
        ).strip()
        if (
            charset_policy == "strict"
            and glyph_injection_enabled
            and SMSGlyphInjector is not None
            and str(rom_path).lower().endswith((".sms", ".gg", ".sg"))
        ):
            try:
                _crc_upper = str(crc_before).upper()
                injector = SMSGlyphInjector(
                    rom,
                    _crc_upper,
                    rom_size,
                    font_hint=glyph_font,
                )
                if injector.has_font_regions():
                    tbl = self._get_tbl_loader()
                    if tbl is not None:
                        missing = injector.detect_missing_chars(
                            str(translated_path), tbl
                        )
                        # Also inject if TBL has accent mappings but tiles are empty
                        needs_tiles = injector.needs_font_tile_injection(tbl)
                        if missing or needs_tiles:
                            # For tile injection, use all PT-BR accent chars
                            inject_set = missing if missing else set()
                            glyph_injection_report = injector.inject_glyphs(
                                inject_set, tbl
                            )
                            if glyph_injection_report.get("success"):
                                if DEBUG:
                                    inj_count = glyph_injection_report.get("injected_count", 0)
                                    print(f"[GLYPH_INJECT] {inj_count} accents injected")
                            else:
                                err = glyph_injection_report.get("error", "")
                                if DEBUG:
                                    print(f"[GLYPH_INJECT] FAILED: {err}")
                        else:
                            glyph_injection_report = {
                                "success": True,
                                "injected_count": 0,
                                "missing_before": [],
                                "missing_after": [],
                                "note": "All chars and font tiles already covered",
                            }
            except Exception as _glyph_err:
                if DEBUG:
                    print(f"[GLYPH_INJECT] Error: {_glyph_err}")
        # Ranges alterados na etapa de injeção de glifos precisam ser permitidos no diff gate.
        # Isso evita falso bloqueio quando o texto em si está dentro do mapping.
        glyph_diff_ranges = self._compute_diff_ranges(rom_bytes, bytes(rom))
        for rg in glyph_diff_ranges:
            try:
                g_start = int(rg.get("start", -1))
                g_end = int(rg.get("end", -1))
            except Exception:
                continue
            if g_start >= 0 and g_end > g_start:
                glyph_allowed_ranges.append((g_start, g_end))

        if DEBUG:
            print(f"[REINSERT] mapping={mapping_path.name} items={len(self.mapping)}")
            print(f"[REINSERT] translated_items={len(translated)} force_blocked={force_blocked}")

        # Log obrigatório
        lines_count = len(translated)
        if lines_count == 0:
            raise ReinsertionError("Nenhuma linha para reinserção (lines_count=0).")
        if DEBUG:
            print(f"[REINSERT] lines_count={lines_count}")

        translation_input = {
            "path": str(translated_path),
            "format": translated_path.suffix.lower().lstrip("."),
            "exists": translated_path.exists(),
            "target_platform": str(self._target_platform),
            "game_engineering_profile": {
                "enabled": bool(game_engineering_info.get("enabled", False)),
                "has_crc_profile": bool(game_engineering_info.get("has_crc_profile", False)),
                "profile_id": game_engineering_info.get("profile_id"),
                "profile_name": game_engineering_info.get("profile_name"),
                "profile_version": game_engineering_info.get("profile_version"),
                "profile_file": game_engineering_info.get("profile_file"),
            },
        }
        translation_input["strict_crc_safe_mode"] = bool(strict_crc_safe_mode)
        translation_input["strict_crc_safe_mode_policy_enabled"] = bool(strict_policy_enabled)
        translation_input["strict_crc_safe_mode_target_crc32"] = str(strict_target_crc32)
        if strict_crc_safe_mode:
            translation_input["strict_crc_safe_mode_name"] = "DE9F8517_STRICT_INPLACE"
        translation_input["protected_regions_enabled"] = bool(
            protected_integrity_summary.get("enabled", False)
        )
        translation_input["protected_regions_count"] = int(
            protected_integrity_summary.get("protected_regions_count", 0)
        )
        translation_input["protected_backup_bytes"] = int(
            protected_integrity_summary.get("protected_backup_bytes", 0)
        )
        translation_input["protected_mutable_ranges_count"] = int(
            protected_integrity_summary.get("protected_mutable_ranges_count", 0)
        )
        translation_input["protected_excluded_bytes"] = int(
            protected_integrity_summary.get("protected_excluded_bytes", 0)
        )
        guardrail_warnings = self._collect_guardrail_warnings()
        if strict_crc_safe_mode:
            guardrail_warnings.append(
                "Modo seguro DE9F8517 ativo: sem repoint/realocacao e sem patch de blocos comprimidos."
            )
        translation_input["policy_defaults_active"] = True
        translation_input["guardrail_warnings"] = list(guardrail_warnings)
        translation_input["guardrail_warning_count"] = int(len(guardrail_warnings))
        stats["GUARDRAIL_WARN"] = int(len(guardrail_warnings))
        translation_input["glyph_injection_enabled"] = bool(
            self._coerce_bool(
                self._translation_runtime_policy.get("glyph_injection_enabled"),
                True,
            )
        )
        if strict_crc_safe_mode:
            translation_input["glyph_injection_enabled"] = False
            translation_input["glyph_injection_forced_off_reason"] = "strict_crc_safe_mode"
        translation_input["glyph_font"] = str(
            self._translation_runtime_policy.get("glyph_font", "Verdana.ttf") or "Verdana.ttf"
        ).strip()
        if translated_path.exists():
            translation_input["size_bytes"] = translated_path.stat().st_size
            translation_input["sha256"] = hashlib.sha256(
                translated_path.read_bytes()
            ).hexdigest()
        if isinstance(delta_context, dict) and delta_context:
            translation_input["delta_mode"] = True
            translation_input["delta_path"] = delta_context.get("delta_path")
            translation_input["delta_source_path"] = delta_context.get("source_path")
            translation_input["delta_problem_keys_total"] = int(
                delta_context.get("problem_keys_total", len(translated))
            )

        jsonl_identity = {"rom_crc32": None, "rom_size": None}
        input_match_check = {
            "rom_crc32_match": True,
            "rom_size_match": True,
            "jsonl_declared_crc32": None,
            "jsonl_declared_size": None,
        }
        if translated_path.suffix.lower() == ".jsonl":
            jsonl_identity = self._extract_jsonl_identity(translated_path)
            declared_crc = str(jsonl_identity.get("rom_crc32") or "").upper() or None
            declared_size = self._parse_optional_int_value(jsonl_identity.get("rom_size"))
            input_match_check["jsonl_declared_crc32"] = declared_crc
            input_match_check["jsonl_declared_size"] = declared_size
            input_match_check["rom_crc32_match"] = bool(declared_crc and declared_crc == crc_before.upper())
            input_match_check["rom_size_match"] = bool(
                declared_size is not None and int(declared_size) == int(rom_size)
            )

            translation_input["jsonl_declared_crc32"] = declared_crc
            translation_input["jsonl_declared_size"] = declared_size
            translation_input["rom_crc32_runtime"] = crc_before.upper()
            translation_input["rom_size_runtime"] = int(rom_size)

            if declared_crc is None or declared_size is None:
                raise ReinsertionError(
                    "JSONL traduzido sem metadados obrigatórios rom_crc32/rom_size. "
                    f"Arquivo: {translated_path}"
                )
            if not input_match_check["rom_crc32_match"] or not input_match_check["rom_size_match"]:
                runtime_name_upper = str(Path(rom_path).name).upper()
                is_font_variant_runtime = "_FONT_PTBR" in runtime_name_upper
                allow_font_variant_crc = bool(
                    is_font_variant_runtime and input_match_check["rom_size_match"]
                )
                translation_input["font_variant_runtime"] = bool(is_font_variant_runtime)
                translation_input["font_variant_crc_relaxed"] = bool(allow_font_variant_crc)
                if allow_font_variant_crc:
                    input_match_check["rom_crc32_match"] = True
                else:
                    raise ReinsertionError(
                        "JSONL traduzido pertence a outra ROM "
                        f"(declared_crc32={declared_crc}, declared_size={declared_size}, "
                        f"runtime_crc32={crc_before.upper()}, runtime_size={rom_size})."
                    )

        # Auditoria de cobertura (originais vs traduzidos)
        coverage = {
            "missing_in_translated": 0,
            "empty_translated": 0,
            "same_as_source_raw": 0,
            "untranslated_same_as_source": 0,
            "same_as_source_non_actionable": 0,
            "translated_ok": 0,
            "samples": {
                "missing_in_translated": [],
                "empty_translated": [],
                "untranslated_same_as_source": [],
                "same_as_source_non_actionable": [],
            },
        }
        prepared_translated: Dict[str, str] = {}
        auto_preserve_charset_like = 0
        auto_reject_llm_refusal = 0
        auto_source_forced_overrides = 0
        self._api_fallback_calls = 0
        self._api_fallback_success = 0
        self._api_fallback_rewrites = 0
        self._custom_dict_rewrites = 0
        for key, value in translated.items():
            raw_value = self._normalize_unicode_nfc(
                value if isinstance(value, str) else str(value)
            )
            if raw_value.strip():
                _, _dict_hits = self._apply_custom_dictionary(raw_value)
                if _dict_hits > 0:
                    self._custom_dict_rewrites += int(_dict_hits)
            src_text = ""
            if isinstance(fallback_entries, dict) and key in fallback_entries:
                src_text = self._extract_source_text(fallback_entries.get(key))

            if src_text and self._is_charset_table_like_text(src_text):
                prepared_translated[key] = str(src_text)
                auto_preserve_charset_like += 1
                continue

            if src_text and self._is_llm_refusal_text(raw_value):
                prepared_translated[key] = str(src_text)
                auto_reject_llm_refusal += 1
                continue

            forced_src_text = self._forced_source_translation_override(src_text)
            if forced_src_text:
                prepared_translated[key] = forced_src_text
                auto_source_forced_overrides += 1
                continue

            engineered_value, eng_steps = self._apply_game_engineering_text(
                raw_value, stage="reinsert"
            )
            if eng_steps > 0:
                self._game_engineering_text_changes += int(eng_steps)
            normalized_value = self._normalize_translation_for_reinsertion(engineered_value)
            prepared_translated[key] = normalized_value if normalized_value else engineered_value

        self._strict_ptbr_changes = 0
        strict_ptbr_info = {
            "enabled": bool(self._strict_ptbr_mode),
            "rewritten": 0,
            "override_file": None,
            "overrides_loaded": 0,
            "changes": [],
        }
        strict_overrides: Dict[str, str] = {}
        if self._strict_ptbr_mode:
            strict_overrides, strict_override_file = self._load_strict_ptbr_overrides(
                translated_path, crc_before.upper()
            )
            strict_ptbr_info["override_file"] = strict_override_file
            strict_ptbr_info["overrides_loaded"] = int(len(strict_overrides))

        if self._strict_ptbr_mode:
            for key in list(prepared_translated.keys()):
                src_text = ""
                if fallback_entries and key in fallback_entries:
                    src_text = (
                        fallback_entries[key].get("text_src")
                        or fallback_entries[key].get("text")
                        or fallback_entries[key].get("original_text")
                        or fallback_entries[key].get("text_original")
                        or ""
                    )
                before = prepared_translated.get(key, "")
                if key in strict_overrides and isinstance(strict_overrides.get(key), str):
                    after = self._normalize_translation_for_reinsertion(strict_overrides.get(key, ""))
                    if not after:
                        after = before
                    change_reason = "override_file"
                else:
                    after = self._coerce_ptbr_line(before, src_text)
                    change_reason = "coerce_ptbr"
                if isinstance(after, str) and after and after != before:
                    prepared_translated[key] = after
                    self._strict_ptbr_changes += 1
                    if len(strict_ptbr_info["changes"]) < 64:
                        strict_ptbr_info["changes"].append(
                            {
                                "key": key,
                                "reason": change_reason,
                                "before": str(before)[:200],
                                "after": str(after)[:200],
                            }
                        )
        strict_ptbr_info["rewritten"] = int(self._strict_ptbr_changes)
        stats["STRICT_PTBR"] = int(self._strict_ptbr_changes)
        translation_input["strict_ptbr_mode"] = bool(self._strict_ptbr_mode)
        translation_input["strict_ptbr_rewritten"] = int(self._strict_ptbr_changes)
        translation_input["strict_ptbr_overrides_loaded"] = int(strict_ptbr_info.get("overrides_loaded", 0))
        translation_input["strict_ptbr_override_file"] = strict_ptbr_info.get("override_file")
        id_override_info = {
            "enabled": bool(
                self._coerce_bool(
                    self._translation_runtime_policy.get("id_override_enabled"),
                    True,
                )
            ),
            "override_file": None,
            "overrides_loaded": 0,
            "matched": 0,
            "rewritten": 0,
            "propagated": 0,
            "keys": [],
            "changes": [],
            "warnings": [],
        }
        id_override_keys = set()
        translation_input["game_engineering_rewritten"] = int(self._game_engineering_text_changes)
        translation_input["auto_preserve_charset_like"] = int(auto_preserve_charset_like)
        translation_input["auto_reject_llm_refusal"] = int(auto_reject_llm_refusal)
        translation_input["auto_source_forced_overrides"] = int(auto_source_forced_overrides)
        translation_input["normalize_nfc"] = bool(
            self._coerce_bool(
                self._translation_runtime_policy.get("normalize_nfc"), True
            )
        )
        translation_input["custom_dictionary_path"] = self._custom_dict_path
        translation_input["custom_dictionary_entries"] = int(len(self._custom_dictionary))
        translation_input["custom_dictionary_rewrites"] = int(self._custom_dict_rewrites)
        translation_input["translation_api_fallback"] = bool(
            self._coerce_bool(
                self._translation_runtime_policy.get("translation_api_fallback"), True
            )
        )
        translation_input["translation_service"] = str(
            self._translation_runtime_policy.get("translation_service", "google")
        )
        translation_input["translation_api_max_chars"] = int(
            self._parse_int_value(
                self._translation_runtime_policy.get("translation_api_max_chars", 600),
                default=600,
            )
        )
        translation_input["translation_api_calls"] = int(self._api_fallback_calls)
        translation_input["translation_api_success"] = int(self._api_fallback_success)
        translation_input["translation_api_rewrites"] = int(self._api_fallback_rewrites)
        translation_input["game_engineering_compression"] = (
            dict(compression_policy) if isinstance(compression_policy, dict) else {}
        )
        translation_input["glyph_injection_report"] = (
            dict(glyph_injection_report) if isinstance(glyph_injection_report, dict) else {}
        )
        stats["GAME_ENGINEERING_REWRITE"] = int(self._game_engineering_text_changes)

        auto_pt_fragment_rewrites = 0
        if fallback_entries:
            for key in list(prepared_translated.keys()):
                meta = fallback_entries.get(key) if isinstance(fallback_entries, dict) else None
                if self._is_ui_meta_entry(meta if isinstance(meta, dict) else None):
                    # UI usa template de bytes; não auto-reescrever aqui para não estourar slot.
                    continue
                src_text = self._extract_source_text(meta)
                if not src_text.strip():
                    continue
                is_non_plausible = self._is_non_plausible_text_meta(meta)
                placeholder_candidate = self._is_placeholder_review_candidate(meta, src_text=src_text)
                if is_non_plausible and (not placeholder_candidate):
                    continue
                dst_text = str(prepared_translated.get(key, "") or "")
                if self._normalize_compare_text(dst_text) != self._normalize_compare_text(src_text):
                    continue
                if not self._is_actionable_untranslated_same_source(src_text, dst_text):
                    continue
                auto_pt = self._fragment_autotranslate_pt(src_text)
                if not auto_pt.strip():
                    continue
                src_tokens = self._extract_tokens(src_text)
                if src_tokens and not self._tokens_present(auto_pt, src_tokens):
                    continue
                if self._normalize_compare_text(auto_pt) == self._normalize_compare_text(src_text):
                    continue
                prepared_translated[key] = auto_pt
                auto_pt_fragment_rewrites += 1
        translation_input["auto_pt_fragment_rewrites"] = int(auto_pt_fragment_rewrites)
        auto_non_pt_rewrites = 0
        if fallback_entries:
            for key in list(prepared_translated.keys()):
                meta = fallback_entries.get(key) if isinstance(fallback_entries, dict) else None
                if self._is_ui_meta_entry(meta if isinstance(meta, dict) else None):
                    continue
                src_text = self._extract_source_text(meta)
                is_non_plausible = self._is_non_plausible_text_meta(meta)
                placeholder_candidate = self._is_placeholder_review_candidate(meta, src_text=src_text)
                if is_non_plausible and (not placeholder_candidate):
                    continue
                dst_text = str(prepared_translated.get(key, "") or "")
                if not dst_text.strip():
                    continue
                current_info = self._classify_language_line(dst_text)
                if bool(current_info.get("is_ptbr", False)):
                    continue
                if bool(current_info.get("is_noise", False)):
                    continue
                cand = self._fragment_autotranslate_pt(dst_text)
                if self._normalize_compare_text(cand) == self._normalize_compare_text(dst_text):
                    cand = self._fragment_autotranslate_pt(src_text or dst_text)
                if not cand.strip():
                    continue
                if self._normalize_compare_text(cand) == self._normalize_compare_text(dst_text):
                    continue
                cand_info = self._classify_language_line(cand)
                improves = (
                    int(cand_info.get("pt_score", 0)) > int(current_info.get("pt_score", 0))
                    or bool(cand_info.get("is_ptbr", False))
                )
                if not improves:
                    continue
                src_tokens = self._extract_tokens(src_text)
                if src_tokens and not self._tokens_present(cand, src_tokens):
                    continue
                prepared_translated[key] = cand
                auto_non_pt_rewrites += 1
        translation_input["auto_non_pt_rewrites"] = int(auto_non_pt_rewrites)
        auto_english_cleanup_rewrites = 0
        if fallback_entries:
            for _pass in range(2):
                changed_in_pass = 0
                for key in list(prepared_translated.keys()):
                    meta = fallback_entries.get(key) if isinstance(fallback_entries, dict) else None
                    if self._is_ui_meta_entry(meta if isinstance(meta, dict) else None):
                        continue
                    src_text = self._extract_source_text(meta)
                    dst_text = str(prepared_translated.get(key, "") or "")
                    if not dst_text.strip():
                        continue
                    is_non_plausible = self._is_non_plausible_text_meta(meta)
                    placeholder_candidate = self._is_placeholder_review_candidate(meta, src_text=src_text)
                    if is_non_plausible and (not placeholder_candidate):
                        continue
                    same_as_src_phrase = (
                        self._normalize_compare_text(dst_text) == self._normalize_compare_text(src_text)
                        and self._looks_phrase_like_text(src_text)
                    )
                    has_en_stopword = self._contains_english_stopwords(dst_text)
                    if not (same_as_src_phrase or has_en_stopword):
                        continue
                    base_text = src_text if same_as_src_phrase else dst_text
                    cand = self._fragment_autotranslate_pt(base_text)
                    if self._normalize_compare_text(cand) == self._normalize_compare_text(dst_text):
                        cand = self._fragment_autotranslate_pt(src_text or dst_text)
                    cand = self._normalize_translation_for_reinsertion(cand)
                    if not cand.strip():
                        continue
                    src_tokens = self._extract_tokens(src_text)
                    if src_tokens and not self._tokens_present(cand, src_tokens):
                        continue
                    if self._normalize_compare_text(cand) == self._normalize_compare_text(dst_text):
                        continue
                    cand_info = self._classify_language_line(cand)
                    if has_en_stopword and self._contains_english_stopwords(cand):
                        if not bool(cand_info.get("is_ptbr", False)):
                            continue
                    prepared_translated[key] = cand
                    auto_english_cleanup_rewrites += 1
                    changed_in_pass += 1
                if changed_in_pass == 0:
                    break
        translation_input["auto_english_cleanup_rewrites"] = int(auto_english_cleanup_rewrites)
        # Reaplica dicionário no final para garantir prioridade máxima em
        # entradas que passaram por reformulações automáticas.
        custom_dict_final_rewrites = 0
        if self._custom_dictionary:
            for key in list(prepared_translated.keys()):
                cur_text = str(prepared_translated.get(key, "") or "")
                if not cur_text.strip():
                    continue
                dict_text, dict_hits = self._apply_custom_dictionary(cur_text)
                if int(dict_hits) <= 0 or not dict_text:
                    continue
                if self._normalize_compare_text(dict_text) == self._normalize_compare_text(cur_text):
                    continue
                prepared_translated[key] = dict_text
                custom_dict_final_rewrites += int(dict_hits)
        if custom_dict_final_rewrites > 0:
            self._custom_dict_rewrites += int(custom_dict_final_rewrites)
        translation_input["custom_dictionary_rewrites_post"] = int(custom_dict_final_rewrites)
        translation_input["custom_dictionary_rewrites"] = int(self._custom_dict_rewrites)
        translation_input["translation_api_calls"] = int(self._api_fallback_calls)
        translation_input["translation_api_success"] = int(self._api_fallback_success)
        translation_input["translation_api_rewrites"] = int(self._api_fallback_rewrites)

        # Override curado por ID (arquivo externo), com prioridade final antes da reinserção.
        if bool(id_override_info.get("enabled")):
            id_overrides, id_override_file, id_override_warnings = self._load_id_overrides(
                translated_path,
                crc_before.upper(),
            )
            id_override_info["override_file"] = id_override_file
            id_override_info["overrides_loaded"] = int(len(id_overrides))
            if id_override_warnings:
                id_override_info["warnings"] = list(id_override_warnings)
            if id_overrides:
                for key, override_text in id_overrides.items():
                    if key not in prepared_translated:
                        continue
                    normalized_override = self._normalize_translation_for_reinsertion(
                        self._normalize_unicode_nfc(override_text)
                    )
                    if not normalized_override:
                        continue
                    before = str(prepared_translated.get(key, "") or "")
                    id_override_keys.add(str(key))
                    id_override_info["keys"].append(str(key))
                    id_override_info["matched"] = int(id_override_info.get("matched", 0)) + 1
                    if self._normalize_compare_text(before) == self._normalize_compare_text(
                        normalized_override
                    ):
                        continue
                    prepared_translated[key] = normalized_override
                    id_override_info["rewritten"] = int(id_override_info.get("rewritten", 0)) + 1
                    if len(id_override_info["changes"]) < 64:
                        id_override_info["changes"].append(
                            {
                                "key": str(key),
                                "before": str(before)[:200],
                                "after": str(normalized_override)[:200],
                            }
                        )
                # Propaga override para aliases sobrepostos no mesmo offset,
                # priorizando o slot maior para evitar "cauda" em inglês.
                if isinstance(fallback_entries, dict) and fallback_entries:
                    entry_cache_for_override: Dict[str, Optional[MapEntry]] = {}

                    def _entry_for_override_key(_key: str) -> Optional[MapEntry]:
                        _k = str(_key)
                        if _k in entry_cache_for_override:
                            return entry_cache_for_override.get(_k)
                        _entry = self.mapping.get(_k)
                        if _entry is None:
                            _meta = fallback_entries.get(_k)
                            if isinstance(_meta, dict) and _meta:
                                _entry = self._mapentry_from_jsonl(_k, _meta)
                        entry_cache_for_override[_k] = (
                            _entry if isinstance(_entry, MapEntry) else None
                        )
                        return entry_cache_for_override.get(_k)

                    for source_key in list(id_override_keys):
                        src_entry = _entry_for_override_key(source_key)
                        if not isinstance(src_entry, MapEntry):
                            continue
                        src_text = str(prepared_translated.get(source_key, "") or "").strip()
                        if not src_text:
                            continue
                        src_meta = fallback_entries.get(source_key)
                        src_span = int(
                            self._resolve_entry_slot_total_len(
                                src_entry,
                                src_meta if isinstance(src_meta, dict) else None,
                            )
                        )
                        src_offset = int(src_entry.offset)
                        for cand_key, cand_meta in fallback_entries.items():
                            cand_key_s = str(cand_key)
                            if cand_key_s == str(source_key):
                                continue
                            cand_entry = _entry_for_override_key(cand_key_s)
                            if not isinstance(cand_entry, MapEntry):
                                continue
                            if int(cand_entry.offset) != src_offset:
                                continue
                            cand_span = int(
                                self._resolve_entry_slot_total_len(
                                    cand_entry,
                                    cand_meta if isinstance(cand_meta, dict) else None,
                                )
                            )
                            if cand_span < src_span:
                                continue
                            cand_src_text = self._extract_source_text(
                                cand_meta if isinstance(cand_meta, dict) else None
                            )
                            cand_tokens = self._extract_tokens(cand_src_text)
                            if cand_tokens and not self._tokens_present(src_text, cand_tokens):
                                # Não propaga texto curto para bloco com tokens obrigatórios.
                                continue
                            before_cand = str(prepared_translated.get(cand_key_s, "") or "")
                            if (
                                self._normalize_compare_text(before_cand)
                                == self._normalize_compare_text(src_text)
                            ):
                                id_override_keys.add(cand_key_s)
                                continue
                            prepared_translated[cand_key_s] = src_text
                            id_override_keys.add(cand_key_s)
                            id_override_info["propagated"] = int(
                                id_override_info.get("propagated", 0)
                            ) + 1
                            if len(id_override_info["changes"]) < 64:
                                id_override_info["changes"].append(
                                    {
                                        "key": cand_key_s,
                                        "before": str(before_cand)[:200],
                                        "after": str(src_text)[:200],
                                        "reason": f"propagated_from={source_key}",
                                    }
                                )

        translation_input["id_override_enabled"] = bool(id_override_info.get("enabled", False))
        translation_input["id_override_file"] = id_override_info.get("override_file")
        translation_input["id_override_overrides_loaded"] = int(
            id_override_info.get("overrides_loaded", 0)
        )
        translation_input["id_override_matched"] = int(id_override_info.get("matched", 0))
        translation_input["id_override_rewritten"] = int(id_override_info.get("rewritten", 0))
        translation_input["id_override_propagated"] = int(id_override_info.get("propagated", 0))
        translation_input["id_override_warning_count"] = int(
            len(id_override_info.get("warnings", []) or [])
        )
        stats["ID_OVERRIDE"] = int(id_override_info.get("rewritten", 0))
        stats["ID_OVERRIDE_PROPAGATED"] = int(id_override_info.get("propagated", 0))

        # Cobre entradas de UI sobrepostas que não vieram no JSONL traduzido.
        # Ex.: chaves "filhas" (OVERLAP_DISCARDED) usadas em outro ponteiro do jogo.
        auto_ui_overlap_aliases = 0
        if isinstance(fallback_entries, dict) and fallback_entries:
            entry_cache: Dict[str, Optional[MapEntry]] = {}

            def _entry_for_key(_key: str) -> Optional[MapEntry]:
                _k = str(_key)
                if _k in entry_cache:
                    return entry_cache.get(_k)
                _entry = self.mapping.get(_k)
                if _entry is None:
                    _meta = fallback_entries.get(_k)
                    if isinstance(_meta, dict) and _meta:
                        _entry = self._mapentry_from_jsonl(_k, _meta)
                entry_cache[_k] = _entry if isinstance(_entry, MapEntry) else None
                return entry_cache.get(_k)

            translated_keys_order = [
                str(k)
                for k, v in prepared_translated.items()
                if isinstance(v, str) and str(v).strip()
            ]

            for key, meta in fallback_entries.items():
                k = str(key)
                if str(prepared_translated.get(k, "") or "").strip():
                    continue
                if not isinstance(meta, dict):
                    continue
                source_hint = str(meta.get("source", "") or "")
                if not self._is_ui_meta_entry(meta, source_hint=source_hint):
                    continue
                flags = set(self._normalized_review_flags(meta))
                blocked_reason = str(meta.get("blocked_reason", "") or "").upper()
                if ("OVERLAP_DISCARDED" not in flags) and ("OVERLAP_DISCARDED" not in blocked_reason):
                    continue

                cur_entry = _entry_for_key(k)
                if not isinstance(cur_entry, MapEntry):
                    continue
                cur_start = int(cur_entry.offset)
                cur_end = int(cur_entry.offset) + max(0, int(cur_entry.max_len))
                if cur_end <= cur_start:
                    continue

                cur_kind = str(meta.get("ui_kind", "") or "").strip().upper()
                cur_ctx = str(meta.get("context_tag", "") or "").strip().lower()
                best_key = ""
                best_score: Optional[int] = None

                for cand_key in translated_keys_order:
                    if cand_key == k:
                        continue
                    cand_text = str(prepared_translated.get(cand_key, "") or "")
                    if not cand_text.strip():
                        continue
                    cand_entry = _entry_for_key(cand_key)
                    if not isinstance(cand_entry, MapEntry):
                        continue
                    cand_start = int(cand_entry.offset)
                    cand_end = int(cand_entry.offset) + max(0, int(cand_entry.max_len))
                    if cand_end <= cand_start:
                        continue
                    # Segurança: só alias quando o range for exatamente idêntico.
                    # Overlap parcial (filho dentro do pai) pode corromper UI ao sobrescrever
                    # metade da frase já aplicada.
                    if not (cand_start == cur_start and cand_end == cur_end):
                        continue

                    score = 0
                    cand_meta = fallback_entries.get(cand_key)
                    if isinstance(cand_meta, dict):
                        cand_kind = str(cand_meta.get("ui_kind", "") or "").strip().upper()
                        cand_ctx = str(cand_meta.get("context_tag", "") or "").strip().lower()
                        if cur_kind and cand_kind == cur_kind:
                            score += 100
                        if cur_ctx and cand_ctx and cand_ctx == cur_ctx:
                            score += 50
                    # Prefere o menor "pai" possível para manter contexto equivalente.
                    score -= max(0, int(cand_entry.max_len) - int(cur_entry.max_len))

                    if best_score is None or score > int(best_score):
                        best_score = int(score)
                        best_key = str(cand_key)

                if best_key:
                    alias_text = str(prepared_translated.get(best_key, "") or "").strip()
                    if alias_text:
                        prepared_translated[k] = alias_text
                        translated_keys_order.append(k)
                        auto_ui_overlap_aliases += 1
                        continue

                # Fallback final: tenta override determinístico pelo source.
                forced = self._forced_source_translation_override(self._extract_source_text(meta))
                if isinstance(forced, str) and forced.strip():
                    prepared_translated[k] = forced.strip()
                    translated_keys_order.append(k)
                    auto_ui_overlap_aliases += 1

        translation_input["auto_ui_overlap_aliases"] = int(auto_ui_overlap_aliases)

        if fallback_entries:
            for key, meta in fallback_entries.items():
                src_text = (
                    meta.get("text_src")
                    or meta.get("text")
                    or meta.get("original_text")
                    or meta.get("text_original")
                    or ""
                )
                if not isinstance(src_text, str) or not src_text.strip():
                    continue
                if key not in prepared_translated:
                    coverage["missing_in_translated"] += 1
                    if len(coverage["samples"]["missing_in_translated"]) < 8:
                        coverage["samples"]["missing_in_translated"].append(
                            {"key": key, "src": src_text[:120]}
                        )
                    continue
                dst_text = prepared_translated.get(key, "")
                if not isinstance(dst_text, str) or not dst_text.strip():
                    coverage["empty_translated"] += 1
                    if len(coverage["samples"]["empty_translated"]) < 8:
                        coverage["samples"]["empty_translated"].append(
                            {"key": key, "src": src_text[:120]}
                        )
                    continue
                if self._normalize_compare_text(dst_text) == self._normalize_compare_text(src_text):
                    coverage["same_as_source_raw"] += 1
                    if self._is_actionable_untranslated_same_source(src_text, dst_text):
                        coverage["untranslated_same_as_source"] += 1
                        if len(coverage["samples"]["untranslated_same_as_source"]) < 8:
                            coverage["samples"]["untranslated_same_as_source"].append(
                                {"key": key, "src": src_text[:120], "dst": dst_text[:120]}
                            )
                    else:
                        coverage["same_as_source_non_actionable"] += 1
                        if len(coverage["samples"]["same_as_source_non_actionable"]) < 8:
                            coverage["samples"]["same_as_source_non_actionable"].append(
                                {"key": key, "src": src_text[:120], "dst": dst_text[:120]}
                            )
                    continue
                coverage["translated_ok"] += 1

        ordered_translation_records = self._build_ordered_translation_records(
            prepared_translated, fallback_entries
        )
        ordered_keys = [rec["key"] for rec in ordered_translation_records]
        seq_values = [int(rec["seq"]) for rec in ordered_translation_records if rec.get("seq") is not None]
        seq_consistent = (
            len(seq_values) == len(set(seq_values))
            and seq_values == sorted(seq_values)
        )
        ordering_check = {
            "is_sorted_by_offset": all(
                ordered_translation_records[i]["offset"] <= ordered_translation_records[i + 1]["offset"]
                for i in range(len(ordered_translation_records) - 1)
                if ordered_translation_records[i]["offset"] >= 0
                and ordered_translation_records[i + 1]["offset"] >= 0
            ),
            "seq_consistent": bool(seq_consistent),
            "first_10_offsets": [
                {
                    "seq": rec.get("seq"),
                    "offset": f"0x{int(rec.get('offset', 0)):06X}"
                    if int(rec.get("offset", -1)) >= 0
                    else None,
                    "key": rec.get("key"),
                }
                for rec in ordered_translation_records[:10]
            ],
            "last_10_offsets": [
                {
                    "seq": rec.get("seq"),
                    "offset": f"0x{int(rec.get('offset', 0)):06X}"
                    if int(rec.get("offset", -1)) >= 0
                    else None,
                    "key": rec.get("key"),
                }
                for rec in ordered_translation_records[-10:]
            ],
        }

        if fallback_entries:
            coverage_records = self._build_ordered_meta_records(fallback_entries)
        else:
            coverage_records = [rec for rec in ordered_translation_records if rec.get("offset", -1) >= 0]

        if coverage_records:
            offsets = [int(rec["offset"]) for rec in coverage_records]
            coverage_check = {
                "min_offset": int(min(offsets)),
                "max_offset": int(max(offsets)),
                "items_total": int(len(coverage_records)),
                "count_offsets_below_0x10000": int(sum(1 for off in offsets if off < 0x10000)),
                "first_20_items_summary": [
                    {
                        "seq": rec.get("seq"),
                        "offset": f"0x{int(rec.get('offset', 0)):06X}",
                        "key": rec.get("key"),
                    }
                    for rec in coverage_records[:20]
                ],
            }
        else:
            coverage_check = {
                "min_offset": None,
                "max_offset": None,
                "items_total": 0,
                "count_offsets_below_0x10000": 0,
                "first_20_items_summary": [],
            }

        # Snapshot final dos ajustes de dicionário/API após toda limpeza automática.
        translation_input["custom_dictionary_rewrites"] = int(self._custom_dict_rewrites)
        translation_input["translation_api_calls"] = int(self._api_fallback_calls)
        translation_input["translation_api_success"] = int(self._api_fallback_success)
        translation_input["translation_api_rewrites"] = int(self._api_fallback_rewrites)

        translation_quality = self._build_translation_audit(prepared_translated, fallback_entries)

        ui_meta_by_key: Dict[str, Dict[str, Any]] = {}
        ui_keys: set = set()
        if isinstance(fallback_entries, dict):
            for key, meta in fallback_entries.items():
                source_hint = ""
                if isinstance(meta, dict):
                    source_hint = str(meta.get("source", "") or "")
                if self._is_ui_meta_entry(meta if isinstance(meta, dict) else None, source_hint=source_hint):
                    k = str(key)
                    ui_keys.add(k)
                    if isinstance(meta, dict):
                        ui_meta_by_key[k] = meta
        ui_found_count = int(len(ui_keys))
        ui_extracted_count = int(len(ui_keys))
        ui_translated_count = int(
            sum(1 for k in ui_keys if str(prepared_translated.get(k, "") or "").strip())
        )
        ui_blocked_details: List[Dict[str, Any]] = []

        # Pré-processamento
        tilemap_items: List[Dict[str, Any]] = []
        fits_items: List[Dict[str, Any]] = []
        reloc_items: List[Dict[str, Any]] = []
        not_applied: List[Dict[str, Any]] = []
        pending_hidden_prefix_patches: Dict[str, Dict[str, Any]] = {}
        planned_text_ranges: List[Dict[str, Any]] = []
        charset_stats = {
            "ascii_items": 0,
            "tilemap_items": 0,
            "ascii_fallback_chars": 0,
            "tilemap_fallback_chars": 0,
        }
        compressed_runtime_enabled = bool(MultiDecompress and MultiCompress and CompressionAlgorithm)
        compressed_deferred_keys: set = set()
        protected_pointer_ranges = self._build_pointer_protected_ranges(fallback_entries)
        auto_relocate_if_needed = bool(
            self._coerce_bool(
                self._translation_runtime_policy.get("auto_relocate_if_needed"),
                True,
            )
        )
        if strict_crc_safe_mode:
            auto_relocate_if_needed = False
        translation_input["auto_relocate_if_needed"] = bool(auto_relocate_if_needed)
        if strict_crc_safe_mode:
            translation_input["auto_relocate_forced_off_reason"] = "strict_crc_safe_mode"
        # Regra estrita: se texto ultrapassar o slot original e houver ponteiros,
        # não tenta salvar in-place com "encurtamento mágico". Deve repointar.
        force_repoint_oversize = os.environ.get("NEUROROM_FORCE_REPOINT_OVERSIZE", "1") == "1"
        translation_input["force_repoint_oversize"] = bool(force_repoint_oversize)
        if compressed_runtime_enabled and isinstance(fallback_entries, dict):
            for key in ordered_keys:
                if self._is_compressed_meta_entry(fallback_entries.get(key)):
                    compressed_deferred_keys.add(str(key))

        # Política global: tilemap sem TBL é bloqueado para evitar corrupção visual.
        tilemap_keys_all = [
            str(k)
            for k, e in self.mapping.items()
            if isinstance(e, MapEntry) and str(e.encoding).lower() in ("tile", "tilemap")
        ]
        tilemap_tbl_required = bool(
            self._coerce_bool(
                self._translation_runtime_policy.get("tilemap_require_tbl"), True
            )
        )
        tilemap_fail_fast = bool(
            self._coerce_bool(
                self._translation_runtime_policy.get("tilemap_fail_fast_without_tbl"),
                True,
            )
        )
        translation_input["tilemap_require_tbl"] = tilemap_tbl_required
        translation_input["require_tilemap"] = tilemap_tbl_required
        translation_input["tilemap_fail_fast_without_tbl"] = tilemap_fail_fast
        translation_input["tilemap_entries_detected"] = int(len(tilemap_keys_all))
        if tilemap_tbl_required and tilemap_keys_all:
            tile_tbl_loader = self._get_tbl_loader(require_tilemap=True)
            has_tile_tbl = tile_tbl_loader is not None
            translation_input["tilemap_tbl_available"] = bool(has_tile_tbl)
            if (not has_tile_tbl) and tilemap_fail_fast:
                sample_keys = ", ".join(tilemap_keys_all[:12])
                raise ReinsertionError(
                    "Bloqueio de segurança: entradas tilemap detectadas sem TBL válido. "
                    "Carregue/defina o .tbl correto para este CRC antes da reinserção. "
                    f"Exemplos de chaves: {sample_keys}"
                )
        else:
            translation_input["tilemap_tbl_available"] = True

        # Resolve aliases por offset: aplica primeiro o maior slot do grupo.
        # Isso evita que entradas curtas sobreponham parcialmente blocos longos.
        primary_key_by_offset: Dict[int, str] = {}
        primary_span_by_offset: Dict[int, int] = {}
        offset_group_sizes: Dict[int, int] = {}
        for key in ordered_keys:
            entry_for_group = self.mapping.get(key)
            if entry_for_group is None and isinstance(fallback_entries, dict):
                meta_group = fallback_entries.get(key)
                if isinstance(meta_group, dict) and meta_group:
                    entry_for_group = self._mapentry_from_jsonl(key, meta_group)
                    if isinstance(entry_for_group, MapEntry):
                        self.mapping[key] = entry_for_group
            if not isinstance(entry_for_group, MapEntry):
                continue
            meta_group = fallback_entries.get(key) if isinstance(fallback_entries, dict) else None
            slot_span = int(
                self._resolve_entry_slot_total_len(
                    entry_for_group,
                    meta_group if isinstance(meta_group, dict) else None,
                )
            )
            off_val = int(entry_for_group.offset)
            offset_group_sizes[off_val] = int(offset_group_sizes.get(off_val, 0)) + 1
            cur_key = primary_key_by_offset.get(off_val)
            cur_span = int(primary_span_by_offset.get(off_val, -1))
            replace = False
            if cur_key is None or slot_span > cur_span:
                replace = True
            elif slot_span == cur_span and cur_key is not None:
                if (str(key) in id_override_keys) and (str(cur_key) not in id_override_keys):
                    replace = True
            if replace:
                primary_key_by_offset[off_val] = str(key)
                primary_span_by_offset[off_val] = int(slot_span)
        translation_input["offset_alias_groups"] = int(
            sum(1 for v in offset_group_sizes.values() if int(v) > 1)
        )
        compact_glossary_crc32 = (
            str(
                self.mapping_crc32
                or self._jsonl_declared_crc32
                or crc_before
                or ""
            )
            .strip()
            .upper()
            or None
        )
        strip_accents_before_fit = self._should_strip_accents_for_crc(compact_glossary_crc32)
        translation_input["strip_accents_before_fit"] = bool(strip_accents_before_fit)
        translation_input["strip_accents_crc32"] = str(compact_glossary_crc32 or "")

        for key in ordered_keys:
            if key in compressed_deferred_keys:
                continue
            new_text = prepared_translated.get(key, "")
            # Ordem obrigatória:
            # 1) glossário compacto -> 2) remoção de acentos (quando necessário)
            # 3) somente depois entra no pipeline de fit/truncamento.
            new_text = apply_compact_glossary(new_text, compact_glossary_crc32)
            if strip_accents_before_fit:
                new_text = strip_accents_for_rom(new_text)
            prepared_translated[key] = str(new_text or "")
            entry = self.mapping.get(key)
            if entry is None and isinstance(fallback_entries, dict):
                meta_entry = fallback_entries.get(key)
                if isinstance(meta_entry, dict) and meta_entry:
                    entry = self._mapentry_from_jsonl(key, meta_entry)
                    if isinstance(entry, MapEntry):
                        # Mantém em cache para evitar reprocessamento no mesmo ciclo.
                        self.mapping[key] = entry
            # Não usa scan cego; apenas metadados já presentes no JSONL/mapping.
            if not entry:
                stats["SKIP"] += 1
                stats["SKIP_NO_MAPPING"] += 1
                items_report.append({"key": key, "action": "SKIP_NO_MAPPING", "reason": "mapping não encontrado"})
                continue

            meta = fallback_entries.get(key) if isinstance(fallback_entries, dict) else None
            source_hint = ""
            if isinstance(meta, dict):
                source_hint = str(meta.get("source", "") or "")

            entry_start = int(entry.offset)
            slot_payload_len = int(
                self._resolve_entry_payload_len(
                    entry,
                    meta if isinstance(meta, dict) else None,
                )
            )
            slot_total_len = int(slot_payload_len + (1 if entry.terminator is not None else 0))
            entry_end = entry_start + max(0, slot_total_len)
            primary_key = primary_key_by_offset.get(int(entry_start))
            if primary_key and str(primary_key) != str(key):
                stats["SKIP"] += 1
                stats["SKIP_OFFSET_ALIAS"] = int(stats.get("SKIP_OFFSET_ALIAS", 0)) + 1
                items_report.append(
                    {
                        "key": key,
                        "action": "SKIP_OFFSET_ALIAS",
                        "offset": entry.offset,
                        "max_len": entry.max_len,
                        "reason": f"primary_key={primary_key}",
                    }
                )
                not_applied.append({"key": key, "reason": "offset_alias_small_slot"})
                continue
            if strict_crc_safe_mode and protected_regions and self._range_overlaps_any(
                entry_start, entry_end, protected_regions
            ):
                stats["BLOCKED"] += 1
                stats["BLOCKED_PROTECTED_REGION"] = int(
                    stats.get("BLOCKED_PROTECTED_REGION", 0)
                ) + 1
                items_report.append(
                    {
                        "key": key,
                        "action": "BLOCKED_PROTECTED_REGION",
                        "offset": entry.offset,
                        "max_len": entry.max_len,
                        "reason": "protected_region_overlap",
                    }
                )
                not_applied.append({"key": key, "reason": "protected_region_overlap"})
                continue
            # Regra anti-regressão:
            # se a entrada é sub-string de um bloco maior sem tradução, evita
            # escrita in-place parcial (inglês+português misturado).
            # Para entradas com ponteiro, força realocação; sem ponteiro, bloqueia.
            untranslated_overlap_owner = None
            untranslated_overlap_owner_span = -1
            force_relocate_due_parent_overlap = False
            if entry_end > entry_start:
                current_span = int(entry_end - entry_start)
                owner_candidate_keys = set(str(k) for k in self.mapping.keys())
                if isinstance(fallback_entries, dict):
                    owner_candidate_keys.update(str(k) for k in fallback_entries.keys())
                for owner_key in owner_candidate_keys:
                    if str(owner_key) == str(key):
                        continue
                    owner_meta = (
                        fallback_entries.get(str(owner_key))
                        if isinstance(fallback_entries, dict)
                        else None
                    )
                    owner_entry = self.mapping.get(str(owner_key))
                    if owner_entry is None and isinstance(owner_meta, dict):
                        owner_entry = self._mapentry_from_jsonl(str(owner_key), owner_meta)
                    if not isinstance(owner_entry, MapEntry):
                        continue
                    owner_payload_len = int(
                        self._resolve_entry_payload_len(
                            owner_entry,
                            owner_meta if isinstance(owner_meta, dict) else None,
                        )
                    )
                    owner_total_len = int(
                        owner_payload_len + (1 if owner_entry.terminator is not None else 0)
                    )
                    owner_start = int(owner_entry.offset)
                    owner_end = int(owner_start + max(0, owner_total_len))
                    if owner_end <= owner_start:
                        continue
                    owner_span = int(owner_end - owner_start)
                    if owner_span <= current_span:
                        continue
                    if owner_start <= entry_start and owner_end >= entry_end:
                        owner_text = str(prepared_translated.get(str(owner_key), "") or "").strip()
                        if not owner_text and owner_span > untranslated_overlap_owner_span:
                            untranslated_overlap_owner = str(owner_key)
                            untranslated_overlap_owner_span = int(owner_span)
            if untranslated_overlap_owner:
                # Anti-mistura parcial: se o bloco-pai segue sem tradução,
                # bloqueia qualquer sub-fragmento para evitar PT+EN no mesmo texto.
                stats["SKIP"] += 1
                stats["SKIP_OVERLAP_PARENT_UNTRANSLATED"] = int(
                    stats.get("SKIP_OVERLAP_PARENT_UNTRANSLATED", 0)
                ) + 1
                items_report.append(
                    {
                        "key": key,
                        "action": "SKIP_OVERLAP_PARENT_UNTRANSLATED",
                        "offset": entry.offset,
                        "max_len": entry.max_len,
                        "reason": f"owner_key={untranslated_overlap_owner}",
                    }
                )
                not_applied.append({"key": key, "reason": "overlap_parent_untranslated"})
                continue
            overlap_owner = None
            overlap_owner_len = -1
            overlap_owner_start = -1
            overlap_owner_end = -1
            if entry_end > entry_start:
                current_len = entry_end - entry_start
                for planned in planned_text_ranges:
                    p_start = int(planned.get("start", -1))
                    p_end = int(planned.get("end", -1))
                    if p_end <= p_start:
                        continue
                    if not (entry_end <= p_start or entry_start >= p_end):
                        planned_len = p_end - p_start
                        if planned_len >= current_len and planned_len > overlap_owner_len:
                            overlap_owner = str(planned.get("key", ""))
                            overlap_owner_len = int(planned_len)
                            overlap_owner_start = int(p_start)
                            overlap_owner_end = int(p_end)

            # Prioridade explícita: quando um ID está em override curado, preserva
            # seu slot contra sobreposição de chaves não-curadas.
            if entry_end > entry_start and id_override_keys and (str(key) not in id_override_keys):
                overlap_override_key = None
                for planned in planned_text_ranges:
                    p_key = str(planned.get("key", ""))
                    if p_key not in id_override_keys:
                        continue
                    p_start = int(planned.get("start", -1))
                    p_end = int(planned.get("end", -1))
                    if p_end <= p_start:
                        continue
                    if not (entry_end <= p_start or entry_start >= p_end):
                        overlap_override_key = p_key
                        break
                if overlap_override_key:
                    stats["SKIP"] += 1
                    stats["SKIP_ID_OVERRIDE_PRIORITY"] = int(
                        stats.get("SKIP_ID_OVERRIDE_PRIORITY", 0)
                    ) + 1
                    items_report.append(
                        {
                            "key": key,
                            "action": "SKIP_ID_OVERRIDE_PRIORITY",
                            "offset": entry.offset,
                            "max_len": entry.max_len,
                            "reason": f"overlap_with_override_key={overlap_override_key}",
                        }
                    )
                    not_applied.append(
                        {"key": key, "reason": "id_override_priority_overlap"}
                    )
                    continue

            # Se a chave atual é override curado, ela ganha prioridade sobre
            # um overlap planejado anterior que não esteja curado.
            if (
                overlap_owner
                and (str(key) in id_override_keys)
                and (str(overlap_owner) not in id_override_keys)
            ):
                overlap_owner = None
            allow_ui_overlap_alias = False
            overlap_same_text = False
            overlap_same_offset = False
            overlap_current_covers_owner = False
            if overlap_owner:
                owner_meta = (
                    fallback_entries.get(str(overlap_owner))
                    if isinstance(fallback_entries, dict)
                    else None
                )
                owner_source = ""
                if isinstance(owner_meta, dict):
                    owner_source = str(owner_meta.get("source", "") or "")
                cur_flags = set(self._normalized_review_flags(meta))
                cur_is_ui = self._is_ui_meta_entry(
                    meta if isinstance(meta, dict) else None,
                    source_hint=source_hint,
                )
                owner_is_ui = self._is_ui_meta_entry(
                    owner_meta if isinstance(owner_meta, dict) else None,
                    source_hint=owner_source,
                )
                same_range = (
                    overlap_owner_start == entry_start
                    and overlap_owner_end == entry_end
                    and overlap_owner_start >= 0
                    and overlap_owner_end > overlap_owner_start
                )
                overlap_same_offset = (
                    overlap_owner_start == entry_start
                    and overlap_owner_start >= 0
                )
                owner_text_norm = self._normalize_compare_text(
                    str(prepared_translated.get(str(overlap_owner), "") or "")
                )
                cur_text_norm = self._normalize_compare_text(str(new_text or ""))
                same_text = bool(owner_text_norm and owner_text_norm == cur_text_norm)
                overlap_same_text = bool(same_text)
                overlap_current_covers_owner = bool(
                    overlap_same_offset
                    and (entry_end >= overlap_owner_end)
                    and (entry_end > entry_start)
                )
                if (
                    cur_is_ui
                    and owner_is_ui
                    and ("OVERLAP_DISCARDED" in cur_flags)
                    and same_range
                    and same_text
                ):
                    allow_ui_overlap_alias = True
            if overlap_owner and (not allow_ui_overlap_alias):
                allow_override_overlap = bool(
                    (str(key) in id_override_keys)
                    and overlap_current_covers_owner
                    and overlap_same_text
                )
                if allow_override_overlap:
                    overlap_owner = None
                else:
                    stats["SKIP"] += 1
                    stats["SKIP_OVERLAP"] = int(stats.get("SKIP_OVERLAP", 0)) + 1
                    items_report.append(
                        {
                            "key": key,
                            "action": "SKIP_OVERLAP",
                            "offset": entry.offset,
                            "max_len": entry.max_len,
                            "reason": f"overlap_with_key={overlap_owner}",
                        }
                    )
                    not_applied.append({"key": key, "reason": "overlap_existing_range"})
                    continue

            ui_meta = ui_meta_by_key.get(str(key)) if isinstance(ui_meta_by_key, dict) else None
            is_ui_item = bool(
                str(key) in ui_keys
                or self._is_ui_meta_entry(meta if isinstance(meta, dict) else ui_meta, source_hint=source_hint)
            )
            # Proteção de boot: não aplicar fontes inseguras (preview/opcode/compressão parcial)
            # no bloco crítico de inicialização.
            source_upper = str(source_hint or "").upper()
            review_flags_upper = set(self._normalized_review_flags(meta))
            # Regra de segurança:
            # - blocos de preview/decompressão heurística continuam sempre bloqueados;
            # - SCRIPT_OPCODE_AUTO inseguro bloqueia no modo padrão;
            #   no modo force_blocked permitimos seguir para o gate normal de segurança.
            script_opcode_source = "SCRIPT_OPCODE_AUTO" in source_upper
            script_opcode_unsafe = script_opcode_source and (not bool(entry.reinsertion_safe))
            script_opcode_hard_block = script_opcode_unsafe and (not bool(force_blocked))
            preview_heuristic_hard_block = (
                "DECOMPRESSED_PREVIEW_AUTO" in source_upper
                or "DECOMPRESSED_TABLE_HEURISTIC_AUTO" in source_upper
            )
            proprietary_recompression_hard_block = (
                (not bool(entry.reinsertion_safe))
                and (
                    "PROPRIETARY_DECOMPRESSED" in review_flags_upper
                    or "REQUIRES_RECOMPRESSION" in review_flags_upper
                )
                and (not bool(force_blocked))
            )
            hard_unsafe_source = (
                preview_heuristic_hard_block
                or script_opcode_hard_block
                or proprietary_recompression_hard_block
            )
            if hard_unsafe_source:
                stats["SKIP"] += 1
                stats["SKIP_HARD_UNSAFE_SOURCE"] = int(
                    stats.get("SKIP_HARD_UNSAFE_SOURCE", 0)
                ) + 1
                not_applied.append({"key": key, "reason": "hard_unsafe_source_skip"})
                items_report.append(
                    {
                        "key": key,
                        "action": "SKIP_HARD_UNSAFE_SOURCE",
                        "offset": entry.offset,
                        "max_len": entry.max_len,
                        "reason": f"source={source_hint or 'UNKNOWN'}",
                    }
                )
                continue
            orig_text = ""
            review_autounblock = False
            review_autounblock_reason = None
            candidate_allowed = False
            if meta:
                orig_text = (
                    meta.get("text_src")
                    or meta.get("text")
                    or meta.get("original_text")
                    or meta.get("text_original")
                    or ""
                )
                if not isinstance(orig_text, str):
                    orig_text = ""
                if bool(meta.get("needs_review", False)) and (str(key) not in id_override_keys):
                    review_flags_all = set(self._normalized_review_flags(meta))
                    if (
                        not bool(entry.reinsertion_safe)
                        and any("FRAGMENT" in str(flag).upper() for flag in review_flags_all)
                        and not bool(force_blocked)
                    ):
                        stats["SKIP"] += 1
                        not_applied.append({"key": key, "reason": "prefix_fragment_skip"})
                        items_report.append(
                            {
                                "key": key,
                                "action": "SKIP_FRAGMENT",
                                "reason": "prefix_fragment_flag",
                            }
                        )
                        continue
                    allow_non_plausible_autounblock = self._is_placeholder_review_candidate(
                        meta,
                        src_text=orig_text,
                    )
                    if self._is_non_plausible_text_meta(meta) and not allow_non_plausible_autounblock:
                        stats["SKIP"] += 1
                        not_applied.append({"key": key, "reason": "nontext_skip"})
                        items_report.append(
                            {
                                "key": key,
                                "action": "SKIP_NONPLAUSIBLE",
                                "reason": "needs_review_non_plausible",
                            }
                        )
                        continue
                    allowed, candidate_text, reason_tag = self._can_autounblock_review_fragment(
                        meta=meta,
                        src_text=orig_text,
                        dst_text=str(new_text),
                    )
                    candidate_allowed = bool(allowed)
                    if not allowed:
                        review_flags = set(self._normalized_review_flags(meta))
                        if (
                            any("FRAGMENT" in str(flag).upper() for flag in review_flags)
                            and not bool(force_blocked)
                        ):
                            stats["SKIP"] += 1
                            not_applied.append({"key": key, "reason": "prefix_fragment_skip"})
                            items_report.append(
                                {
                                    "key": key,
                                    "action": "SKIP_FRAGMENT",
                                    "reason": "prefix_fragment_flag",
                                }
                            )
                            continue
                        src_compact = re.sub(r"\s+", " ", str(orig_text or "")).strip()
                        short_fragment = self._is_non_standalone_prefix_fragment(
                            src_compact,
                            review_flags=review_flags,
                        )
                        if short_fragment and not bool(force_blocked):
                            stats["SKIP"] += 1
                            not_applied.append({"key": key, "reason": "prefix_fragment_skip"})
                            items_report.append(
                                {
                                    "key": key,
                                    "action": "SKIP_FRAGMENT",
                                    "reason": "prefix_fragment_skip",
                                }
                            )
                            continue
                        src_fallback = re.sub(r"\s+", " ", str(orig_text or "")).strip()
                        if src_fallback:
                            if bool(force_blocked):
                                # Em modo forçado, tenta traduzir fragmentos automaticamente
                                # antes de cair no fallback cru do source.
                                auto_pt = self._fragment_autotranslate_pt(src_fallback)
                                auto_pt_norm = self._normalize_compare_text(auto_pt)
                                src_fb_norm = self._normalize_compare_text(src_fallback)
                                if (
                                    auto_pt_norm
                                    and auto_pt_norm != src_fb_norm
                                    and not self._is_probable_nontext_garbage(auto_pt)
                                ):
                                    src_fallback = auto_pt
                                    review_autounblock_reason = "needs_review_fallback_autopt"
                                else:
                                    review_autounblock_reason = "needs_review_fallback_source"
                            else:
                                review_autounblock_reason = "needs_review_fallback_source"
                            # Cobertura 1:1: quando review falha heurística, aplica fallback no source.
                            new_text = src_fallback
                            prepared_translated[key] = src_fallback
                            review_autounblock = True
                        else:
                            not_applied.append({"key": key, "reason": "needs_review"})
                            stats["BLOCKED"] += 1
                            items_report.append(
                                {"key": key, "action": "NOT_APPLIED", "reason": "needs_review"}
                            )
                            continue
                    if candidate_allowed and isinstance(candidate_text, str) and candidate_text.strip():
                        new_text = candidate_text
                        prepared_translated[key] = candidate_text
                    review_autounblock = True
                    review_autounblock_reason = reason_tag

            hidden_prefix_ctx = self._detect_hidden_ctrl_prefix_fragment(
                rom_data=rom,
                entry=entry,
                source_text=orig_text,
            )
            if hidden_prefix_ctx and bool(hidden_prefix_ctx.get("suspicious_fragment")):
                ptbr_fix = self._suggest_ptbr_hidden_prefix_fix(
                    prefix_text=str(hidden_prefix_ctx.get("prefix_text", "")),
                    translated_text=str(new_text),
                )
                if ptbr_fix is not None:
                    prefix_text_fix, text_fix = ptbr_fix
                    patch_slots = hidden_prefix_ctx.get("slots", []) or []
                    pending_hidden_prefix_patches[str(key)] = {
                        "slots": patch_slots,
                        "text": prefix_text_fix,
                    }
                    if patch_slots:
                        start_slot = min(int(s) for s in patch_slots)
                        end_slot = max(int(s) for s in patch_slots) + 1
                        planned_text_ranges.append(
                            {
                                "key": key,
                                "start": int(start_slot),
                                "end": int(end_slot),
                                "reason": "hidden_prefix_patch",
                            }
                        )
                    if isinstance(text_fix, str):
                        new_text = text_fix
                        prepared_translated[key] = text_fix
                    stats["HIDDEN_PREFIX_FIX"] = int(stats.get("HIDDEN_PREFIX_FIX", 0)) + 1
                elif not bool(force_blocked):
                    stats["SKIP"] += 1
                    stats["SKIP_HIDDEN_PREFIX"] = int(stats.get("SKIP_HIDDEN_PREFIX", 0)) + 1
                    not_applied.append({"key": key, "reason": "hidden_prefix_fragment"})
                    items_report.append(
                        {
                            "key": key,
                            "action": "SKIP_HIDDEN_PREFIX",
                            "reason": "hidden_prefix_fragment",
                        }
                    )
                    continue

            tokens = self._extract_tokens(orig_text)
            if tokens and not self._tokens_present(str(new_text), tokens):
                not_applied.append({"key": key, "reason": "token_mismatch"})
                stats["BLOCKED"] += 1
                items_report.append(
                    {"key": key, "action": "NOT_APPLIED", "reason": "token_mismatch"}
                )
                continue

            # Enriquecimento de ponteiros via JSONL (corrige refs genéricas do mapping)
            if fallback_entries:
                fref = fallback_entries.get(key)
                can_enrich_refs = (not entry.pointer_refs) or self._refs_are_generic(
                    entry.pointer_refs, entry.pointer_offsets
                )
                if can_enrich_refs and fref and fref.get("pointer_refs"):
                    refs = []
                    for ref in fref.get("pointer_refs", []) or []:
                        poff = self._parse_int_value(ref.get("ptr_offset"), default=-1)
                        if poff < 0:
                            continue
                        refs.append(
                            {
                                "ptr_offset": int(poff),
                                "ptr_size": self._parse_int_value(ref.get("ptr_size", 2), default=2),
                                "endianness": str(ref.get("endianness", "little")).lower(),
                                "addressing_mode": str(ref.get("addressing_mode", "ABSOLUTE")),
                                "bank_addend": self._parse_int_value(ref.get("bank_addend", 0), default=0),
                            }
                        )
                    if refs:
                        refs, rejected_ptr_overlap = self._filter_pointer_refs_for_safety(
                            refs,
                            protected_pointer_ranges,
                        )
                        if rejected_ptr_overlap > 0:
                            stats["PTR_REF_REJECTED_TEXT_OVERLAP"] = int(
                                stats.get("PTR_REF_REJECTED_TEXT_OVERLAP", 0)
                            ) + int(rejected_ptr_overlap)
                        if refs:
                            entry.pointer_refs = refs
                            entry.pointer_offsets = [int(r["ptr_offset"]) for r in refs]
                            entry.has_pointer = True
                            stats["PTR_FROM_META"] += 1
            if entry.pointer_refs:
                filtered_existing_refs, rejected_existing = self._filter_pointer_refs_for_safety(
                    list(entry.pointer_refs or []),
                    protected_pointer_ranges,
                )
                if rejected_existing > 0:
                    stats["PTR_REF_REJECTED_TEXT_OVERLAP"] = int(
                        stats.get("PTR_REF_REJECTED_TEXT_OVERLAP", 0)
                    ) + int(rejected_existing)
                    entry.pointer_refs = filtered_existing_refs
                    entry.pointer_offsets = [
                        int(r["ptr_offset"])
                        for r in filtered_existing_refs
                        if self._parse_optional_int_value(r.get("ptr_offset")) is not None
                    ]
                    entry.has_pointer = bool(entry.pointer_refs)

            entry_errors = self._validate_entry(entry, rom_size)
            if entry_errors:
                stats["BLOCKED"] += 1
                stats["BLOCKED_INVALID"] += 1
                items_report.append(
                    {"key": key, "action": "BLOCKED_INVALID", "offset": entry.offset, "max_len": entry.max_len,
                     "terminator": entry.terminator, "errors": entry_errors}
                )
                continue

            # Guarda dura de boot:
            # nunca permite escrita no vetor/bloco inicial da ROM.
            # Isso evita telas pretas por corrupção em offset 0x000000.
            boot_guard_limit = 0x0200
            if int(entry.offset) < boot_guard_limit:
                stats["BLOCKED"] += 1
                stats["BLOCKED_BANK0"] += 1
                items_report.append(
                    {
                        "key": key,
                        "action": "BLOCKED_BANK0",
                        "offset": entry.offset,
                        "max_len": entry.max_len,
                        "reason": f"boot_guard_below_0x{boot_guard_limit:04X}",
                    }
                )
                not_applied.append({"key": key, "reason": "boot_guard_bank0"})
                continue

            is_tilemap = entry.encoding in ("tile", "tilemap")
            overlap_ui_autounblock = False
            unsafe_reason_upper = str(entry.blocked_reason or "").strip().upper()
            if (
                is_ui_item
                and (not bool(entry.reinsertion_safe))
                and (
                    ("OVERLAP_DISCARDED" in unsafe_reason_upper)
                    or ("OVERLAP_DISCARDED" in review_flags_upper)
                )
            ):
                overlap_ui_autounblock = True
                review_autounblock = True
                if not review_autounblock_reason:
                    review_autounblock_reason = "ui_overlap_autounblock"

            if (
                not entry.reinsertion_safe
                and not force_blocked
                and not is_tilemap
                and not review_autounblock
            ):
                unsafe_reason = str(entry.blocked_reason or "reinsertion_safe=false")
                if unsafe_reason.strip().upper() == "NOT_PLAUSIBLE_TEXT_SMS":
                    stats["SKIP"] += 1
                    items_report.append(
                        {
                            "key": key,
                            "action": "SKIP_NONPLAUSIBLE",
                            "offset": entry.offset,
                            "max_len": entry.max_len,
                            "reason": unsafe_reason,
                        }
                    )
                    not_applied.append({"key": key, "reason": "nontext_skip"})
                    continue
                stats["BLOCKED"] += 1
                stats["BLOCKED_UNSAFE"] += 1
                items_report.append(
                    {"key": key, "action": "BLOCKED_UNSAFE", "offset": entry.offset, "max_len": entry.max_len,
                     "reason": unsafe_reason}
                )
                continue
            if review_autounblock:
                stats["AUTO_UNBLOCK_REVIEW"] += 1
                items_report.append(
                    {
                        "key": key,
                        "action": "AUTO_UNBLOCK_REVIEW",
                        "offset": entry.offset,
                        "max_len": entry.max_len,
                        "reason": review_autounblock_reason or "fragment_autounblock",
                    }
                )

            # Ordem obrigatória antes de qualquer fit/truncamento:
            # glossário compacto -> strip de acentos -> pipeline de tamanho.
            new_text = apply_compact_glossary(new_text, compact_glossary_crc32)
            if strip_accents_before_fit:
                new_text = strip_accents_for_rom(new_text)
            prepared_translated[key] = str(new_text or "")

            if is_tilemap:
                tilemap_items.append(
                    {"key": key, "entry": entry, "text": new_text, "orig_text": orig_text}
                )
                planned_text_ranges.append(
                    {"key": key, "start": entry_start, "end": entry_end}
                )
                continue

            is_ctrl_template_item = self._is_control_template_entry(
                entry,
                meta if isinstance(meta, dict) else None,
            )
            if is_ui_item or is_ctrl_template_item:
                template_meta = (
                    ui_meta
                    if (is_ui_item and isinstance(ui_meta, dict))
                    else (meta if isinstance(meta, dict) else {})
                )
                term_value = self._resolve_entry_terminator(
                    entry,
                    template_meta if isinstance(template_meta, dict) else None,
                )
                template_payload, template_fallback_cnt, template_sanitized, template_error = self._build_ui_payload_with_template(
                    str(new_text),
                    template_meta if isinstance(template_meta, dict) else {},
                    term_value,
                )
                if template_error:
                    stats["BLOCKED"] += 1
                    items_report.append(
                        {
                            "key": key,
                            "action": "NOT_APPLIED",
                            "offset": entry.offset,
                            "max_len": entry.max_len,
                            "terminator": term_value,
                            "reason": self._normalize_ui_block_reason(template_error),
                        }
                    )
                    not_applied.append(
                        {
                            "key": key,
                            "reason": self._normalize_ui_block_reason(template_error),
                        }
                    )
                    continue
                if template_payload is None or len(template_payload) > max(0, int(entry.max_len)):
                    stats["BLOCKED"] += 1
                    items_report.append(
                        {
                            "key": key,
                            "action": "NOT_APPLIED",
                            "offset": entry.offset,
                            "max_len": entry.max_len,
                            "terminator": term_value,
                            "reason": "BYTE_OVERFLOW",
                        }
                    )
                    not_applied.append(
                        {
                            "key": key,
                            "reason": "BYTE_OVERFLOW",
                        }
                    )
                    continue
                charset_stats["ascii_fallback_chars"] += int(template_fallback_cnt)
                fits_items.append(
                    {
                        "key": key,
                        "entry": entry,
                        "encoded": bytes(template_payload or b""),
                        "final_text": template_sanitized,
                        "truncated": False,
                        "reformulated": False,
                        "wrapped": False,
                        "strategy": "UI_TEMPLATE" if is_ui_item else "CTRL_TEMPLATE",
                    }
                )
                planned_text_ranges.append(
                    {"key": key, "start": entry_start, "end": entry_end}
                )
                continue

            max_len = max(0, int(slot_payload_len))
            term_value = self._resolve_entry_terminator(
                entry,
                meta if isinstance(meta, dict) else None,
            )
            term = bytes([int(term_value) & 0xFF]) if term_value is not None else b""
            # max_len = bytes de texto (do extractor); terminator vai DEPOIS
            total_space = max_len + len(term)
            payload_limit = max_len  # todos os max_len bytes são para texto

            charset_stats["ascii_items"] += 1

            # Layout box-aware antes de codificar:
            # - respeita largura/linhas
            # - preserva placeholders/tokens
            # - pagina quando token de página estiver disponível
            text_for_encode = str(new_text)
            use_preserve_nl = "\n" in text_for_encode
            layout_wrap_width = self._infer_wrap_width(orig_text, payload_limit)
            if (
                not layout_wrap_width
                and " " in text_for_encode
            ):
                default_width = int(self._get_dialog_defaults().get("width", self.SMS_DEFAULT_DIALOG_WIDTH))
                if len(text_for_encode) > default_width:
                    layout_wrap_width = default_width
            layout_max_lines = self._infer_wrap_max_lines(orig_text)
            layout_page_token = self._infer_page_break_token(orig_text)
            if layout_wrap_width and " " in text_for_encode:
                layout_direct = self._wrap_text_box_aware(
                    text_for_encode,
                    width=int(layout_wrap_width),
                    max_lines=int(layout_max_lines),
                    page_break_token=layout_page_token,
                )
                if bool(layout_direct.get("fits", True)):
                    wrapped_candidate = str(layout_direct.get("text", "") or "").strip()
                    if wrapped_candidate:
                        text_for_encode = wrapped_candidate
                        use_preserve_nl = "\n" in text_for_encode

            encoded_payload, fallback_cnt, sanitized = self._encode_ascii_with_byte_placeholders(
                text_for_encode,
                preserve_newlines=use_preserve_nl,
            )
            encoded_with_term = encoded_payload + term

            if len(encoded_with_term) <= total_space and (not force_relocate_due_parent_overlap):
                _, peak_lines_direct = self._count_layout_lines(
                    sanitized, page_break_token=layout_page_token
                )
                if int(layout_max_lines) <= 0 or int(peak_lines_direct) <= int(layout_max_lines):
                    charset_stats["ascii_fallback_chars"] += fallback_cnt
                    fits_items.append(
                        {
                            "key": key,
                            "entry": entry,
                            "encoded": encoded_with_term,
                            "final_text": sanitized,
                            "truncated": False,
                            "reformulated": False,
                            "wrapped": use_preserve_nl,
                            "strategy": "DIRECT_WRAP" if use_preserve_nl else "DIRECT",
                        }
                    )
                    planned_text_ranges.append(
                        {"key": key, "start": entry_start, "end": entry_end}
                    )
                    continue

            # Tenta compressao DTE antes de truncar/realocar
            if (not force_relocate_due_parent_overlap) and hasattr(self, '_dte_helper') and self._dte_helper:
                dte_result = self._dte_helper.try_dte_compression(
                    encoded_with_term, total_space
                )
                if dte_result is not None:
                    charset_stats["ascii_fallback_chars"] += fallback_cnt
                    fits_items.append(
                        {
                            "key": key,
                            "entry": entry,
                            "encoded": dte_result,
                            "final_text": sanitized,
                            "truncated": False,
                            "reformulated": False,
                            "wrapped": False,
                            "strategy": "DTE",
                        }
                    )
                    planned_text_ranges.append(
                        {"key": key, "start": entry_start, "end": entry_end}
                    )
                    continue

            if entry.pointer_refs and (not force_repoint_oversize) and (not force_relocate_due_parent_overlap):
                # Mantém qualidade quando possível (sem abreviações agressivas).
                fit_soft = self._fit_ascii_reformulation(
                    text=str(new_text),
                    orig_text=orig_text,
                    payload_limit=payload_limit,
                    term=term,
                    tokens=tokens,
                    allow_compact=False,
                    allow_hard_trim=False,
                )
                if fit_soft:
                    charset_stats["ascii_fallback_chars"] += int(fit_soft.get("fallback_chars", 0))
                    fits_items.append(
                        {
                            "key": key,
                            "entry": entry,
                            "encoded": fit_soft["encoded_with_term"],
                            "final_text": fit_soft.get("sanitized", ""),
                            "truncated": bool(fit_soft.get("hard_trim")),
                            "reformulated": bool(fit_soft.get("reformulated")),
                            "wrapped": str(fit_soft.get("strategy", "")).startswith("WRAP"),
                            "strategy": fit_soft.get("strategy", "REFORM"),
                        }
                    )
                    planned_text_ranges.append(
                        {"key": key, "start": entry_start, "end": entry_end}
                    )
                    continue

            # Sem ponteiro: tenta reformular/abreviar com limite estrito
            if not entry.pointer_refs:
                fit = self._fit_ascii_reformulation(
                    text=str(new_text),
                    orig_text=orig_text,
                    payload_limit=payload_limit,
                    term=term,
                    tokens=tokens,
                    allow_compact=True,
                    allow_hard_trim=True,
                )
                if fit:
                    charset_stats["ascii_fallback_chars"] += int(fit.get("fallback_chars", 0))
                    fits_items.append(
                        {
                            "key": key,
                            "entry": entry,
                            "encoded": fit["encoded_with_term"],
                            "final_text": fit.get("sanitized", ""),
                            "truncated": bool(fit.get("hard_trim")),
                            "reformulated": bool(fit.get("reformulated")),
                            "wrapped": str(fit.get("strategy", "")).startswith("WRAP"),
                            "strategy": fit.get("strategy", "REFORM"),
                        }
                    )
                    planned_text_ranges.append(
                        {"key": key, "start": entry_start, "end": entry_end}
                    )
                    continue

            # Com ponteiros: tenta realocar texto completo
            if entry.pointer_refs and auto_relocate_if_needed:
                charset_stats["ascii_fallback_chars"] += fallback_cnt
                reloc_items.append({"key": key, "entry": entry, "encoded": encoded_with_term,
                                    "sanitized": sanitized, "final_text": sanitized,
                                    "payload_limit": payload_limit, "term": term,
                                    "orig_text": orig_text, "tokens": tokens,
                                    "forced_parent_overlap_relocate": bool(force_relocate_due_parent_overlap)})
                planned_text_ranges.append(
                    {"key": key, "start": entry_start, "end": entry_end}
                )
            elif entry.pointer_refs and not auto_relocate_if_needed:
                charset_stats["ascii_fallback_chars"] += fallback_cnt
                not_applied.append({"key": key, "reason": "auto_relocate_disabled"})
                stats["BLOCKED"] += 1
                stats["BLOCKED_RELOC_DISABLED"] += 1
                items_report.append(
                    {
                        "key": key,
                        "action": "NOT_APPLIED",
                        "offset": entry.offset,
                        "reason": "auto_relocate_disabled",
                    }
                )
                continue
            else:
                charset_stats["ascii_fallback_chars"] += fallback_cnt
                not_applied.append({"key": key, "reason": "layout_overflow"})
                stats["BLOCKED"] += 1
                items_report.append(
                    {"key": key, "action": "NOT_APPLIED", "offset": entry.offset, "reason": "layout_overflow"}
                )
                continue

        # 1) Aplica tilemap in-place
        for item in tilemap_items:
            key = item["key"]
            entry = item["entry"]
            new_text = item["text"]
            max_len = max(0, entry.max_len)
            entry_len = max(1, int(self._tile_entry_len))

            tbl = self._get_tbl_loader(require_tilemap=True)
            if tbl is None:
                not_applied.append({"key": key, "reason": "tilemap_tbl_missing"})
                stats["BLOCKED"] += 1
                stats["TILEMAP_BLOCKED_NO_TBL"] = int(stats.get("TILEMAP_BLOCKED_NO_TBL", 0)) + 1
                items_report.append(
                    {"key": key, "action": "NOT_APPLIED", "reason": "tilemap_tbl_missing"}
                )
                continue
            reverse_map = getattr(tbl, "reverse_map", {}) if tbl else {}
            entry_len = max(1, int(getattr(tbl, "max_entry_len", entry_len)))

            if not reverse_map or entry_len != 2:
                encoded = self._encode(new_text, entry.encoding)
                if len(encoded) > max_len:
                    # evita truncar no meio da palavra
                    short_txt = self._shorten_wordwise(new_text, max_len)
                    if not short_txt:
                        not_applied.append({"key": key, "reason": "layout_overflow"})
                        stats["BLOCKED"] += 1
                        items_report.append(
                            {"key": key, "action": "NOT_APPLIED", "reason": "layout_overflow"}
                        )
                        continue
                    encoded = self._encode(short_txt, entry.encoding)
                    stats["TRUNC"] += 1
                    stats["TRUNC_OVERFLOW"] += 1
                    action = "SHORT"
                else:
                    stats["OK"] += 1
                    action = "OK"

                pad_seq = self._tile_space_seq if self._tile_space_seq else (b"\x00" * entry_len)
                while len(encoded) < max_len:
                    encoded += pad_seq

                rom[entry.offset : entry.offset + max_len] = encoded
                items_report.append(
                    {"key": key, "action": action, "offset": entry.offset, "max_len": entry.max_len,
                     "new_len": len(encoded), "truncated": action in ("TRUNC", "SHORT"), "terminator": None}
                )
                continue

            orig = bytes(rom[entry.offset : entry.offset + max_len])
            cleaned, fallback_cnt = self._sanitize_tilemap_text_with_fallback(new_text, reverse_map)
            charset_stats["tilemap_items"] += 1
            charset_stats["tilemap_fallback_chars"] += fallback_cnt
            if not self._tilemap_roundtrip_ok(cleaned, tbl):
                # Fallback extra: substitui caracteres não codificáveis pelo
                # equivalente ASCII mais próximo e tenta novamente.
                ascii_near, ascii_fb = self._sanitize_ascii_text_with_fallback(
                    new_text,
                    preserve_newlines=False,
                    preserve_diacritics=False,
                )
                cleaned_retry, retry_fb = self._sanitize_tilemap_text_with_fallback(
                    ascii_near,
                    reverse_map,
                )
                charset_stats["tilemap_fallback_chars"] += int(ascii_fb) + int(retry_fb)
                if self._tilemap_roundtrip_ok(cleaned_retry, tbl):
                    cleaned = cleaned_retry
                    items_report.append(
                        {
                            "key": key,
                            "action": "ENCODING_ASCII_FALLBACK",
                            "reason": "tilemap_charmap_fallback",
                        }
                    )
                else:
                    not_applied.append({"key": key, "reason": "charmap_mismatch"})
                    stats["BLOCKED"] += 1
                    items_report.append(
                        {"key": key, "action": "NOT_APPLIED", "reason": "charmap_mismatch"}
                    )
                    continue
            encoded_low = self._encode_tilemap_lowbytes(cleaned, reverse_map)
            max_chars = max_len // entry_len if entry_len else 0
            if len(encoded_low) > max_chars:
                # evita truncar no meio da palavra em tilemap
                if "  " in cleaned:
                    not_applied.append({"key": key, "reason": "layout_overflow"})
                    stats["BLOCKED"] += 1
                    items_report.append(
                        {"key": key, "action": "NOT_APPLIED", "reason": "layout_overflow"}
                    )
                    continue
                short_txt = self._shorten_wordwise(cleaned, max_chars)
                if not short_txt:
                    not_applied.append({"key": key, "reason": "layout_overflow"})
                    stats["BLOCKED"] += 1
                    items_report.append(
                        {"key": key, "action": "NOT_APPLIED", "reason": "layout_overflow"}
                    )
                    continue
                encoded_low = self._encode_tilemap_lowbytes(short_txt, reverse_map)
                stats["TRUNC"] += 1
                stats["TRUNC_OVERFLOW"] += 1
                action = "SHORT"
            else:
                stats["OK"] += 1
                action = "OK"

            space_seq = reverse_map.get(" ")
            space_low = space_seq[0] if space_seq else 0x00

            new_block = bytearray(orig)
            for i in range(max_chars):
                low = encoded_low[i] if i < len(encoded_low) else space_low
                idx = i * entry_len
                if idx < len(new_block):
                    new_block[idx] = low

            rom[entry.offset : entry.offset + max_len] = new_block
            items_report.append(
                {"key": key, "action": action, "offset": entry.offset, "max_len": entry.max_len,
                 "new_len": len(new_block), "truncated": action in ("TRUNC", "SHORT"), "terminator": None}
            )

        # 2) Aplica fits_in_place (inclui modo curto/reformulado)
        def _apply_fit_item(item: Dict[str, Any]):
            key = item["key"]
            entry = item["entry"]
            encoded = bytes(item["encoded"] or b"")
            final_text = item.get("final_text")
            strategy = str(item.get("strategy", "DIRECT"))
            meta_for_key = fallback_entries.get(key) if isinstance(fallback_entries, dict) else None
            raw_len = int(
                self._resolve_entry_payload_len(
                    entry,
                    meta_for_key if isinstance(meta_for_key, dict) else None,
                )
            )

            term_val = self._resolve_entry_terminator(
                entry,
                meta_for_key if isinstance(meta_for_key, dict) else None,
            )
            term_byte = bytes([int(term_val) & 0xFF]) if term_val is not None else b""
            payload = encoded
            if term_byte and payload.endswith(term_byte):
                payload = payload[:-1]
            if len(payload) > raw_len:
                payload = payload[:raw_len]
            payload_core = payload

            if term_byte and term_byte in payload_core:
                # Terminador dentro da parte ativa do payload gera corte prematuro.
                not_applied.append({"key": key, "reason": "terminator_in_payload"})
                stats["BLOCKED"] += 1
                items_report.append(
                    {
                        "key": key,
                        "action": "NOT_APPLIED",
                        "offset": entry.offset,
                        "max_len": entry.max_len,
                        "reason": "terminator_in_payload",
                    }
                )
                return
            if len(payload) < raw_len:
                # Anti-regressão: nunca preserva "cauda" antiga do slot.
                # Sempre sobrescreve o restante com espaços.
                payload = payload + (b"\x20" * (raw_len - len(payload)))

            rom[entry.offset : entry.offset + raw_len] = payload
            if term_byte:
                term_off = int(entry.offset) + int(raw_len)
                if not (0 <= term_off < len(rom)):
                    not_applied.append({"key": key, "reason": "terminator_write_oob"})
                    stats["BLOCKED"] += 1
                    items_report.append(
                        {
                            "key": key,
                            "action": "NOT_APPLIED",
                            "offset": entry.offset,
                            "max_len": entry.max_len,
                            "reason": "terminator_write_oob",
                        }
                    )
                    return
                rom[term_off : term_off + 1] = term_byte
            hidden_prefix_patch = pending_hidden_prefix_patches.get(str(key))
            if hidden_prefix_patch:
                self._apply_hidden_prefix_patch_slots(rom, hidden_prefix_patch)
            if not entry.reinsertion_safe:
                stats["FORCED"] += 1
                action = "FORCED"
            else:
                stats["OK"] += 1
                action = "OK"
            if item.get("wrapped"):
                stats["WRAP"] += 1
                stats["LAYOUT_ADJUSTED"] = int(stats.get("LAYOUT_ADJUSTED", 0)) + 1
                if action == "OK":
                    action = "WRAP"
            if item.get("reformulated"):
                stats["REFORM"] += 1
                stats["LAYOUT_ADJUSTED"] = int(stats.get("LAYOUT_ADJUSTED", 0)) + 1
                if action == "OK":
                    action = "REFORM"
            strategy_upper = str(strategy or "").upper()
            if any(tag in strategy_upper for tag in ("SHORT", "ABBREV", "COMPACT", "INITIALS")):
                stats["LAYOUT_SHORT_STYLE"] = int(stats.get("LAYOUT_SHORT_STYLE", 0)) + 1
            if strategy == "DTE" and action == "OK":
                action = "DTE"
            if item.get("truncated"):
                stats["TRUNC"] += 1
                stats["TRUNC_OVERFLOW"] += 1
                stats["LAYOUT_ADJUSTED"] = int(stats.get("LAYOUT_ADJUSTED", 0)) + 1
                action = "SHORT"
            if isinstance(final_text, str) and final_text.strip():
                prepared_translated[key] = final_text
            items_report.append(
                {"key": key, "action": action, "offset": entry.offset, "max_len": entry.max_len,
                 "raw_len": int(raw_len), "new_len": int(raw_len + (1 if term_byte else 0)), "truncated": bool(item.get("truncated")),
                 "terminator": (int(term_val) if term_val is not None else None), "strategy": strategy}
            )

        applied_fits = 0
        for item in fits_items:
            _apply_fit_item(item)
            applied_fits += 1

        # 3) Realocação em pool único para overflow com ponteiros
        relocated_items: List[Dict[str, Any]] = []
        pool_info: Dict[str, Any] = {}
        relocation_forbidden_ranges: List[Tuple[int, int]] = []
        alignment = int(os.environ.get("NEUROROM_RELOC_ALIGN", "2") or 2)
        if reloc_items:
            relocation_forbidden_ranges = self._build_relocation_forbidden_ranges(
                fallback_entries=fallback_entries,
                rom_size=len(rom),
            )
            total_reloc_bytes = 0
            cursor = 0
            for item in reloc_items:
                cursor = self._align(cursor, alignment)
                cursor += len(item["encoded"])
            total_reloc_bytes = cursor

            pool_start, filler_byte = self._find_free_space(
                bytes(rom),
                total_reloc_bytes,
                filler_bytes=(0xFF, 0x00),
                alignment=alignment,
                forbidden_ranges=relocation_forbidden_ranges,
            )
            # Expansão automática de ROM se não encontrar espaço livre
            allow_expand = os.environ.get("NEUROROM_ALLOW_ROM_EXPAND", "1") == "1"
            if pool_start is None and allow_expand:
                pool_start = self._align(len(rom), alignment)
                filler_byte = 0xFF
                pad = max(0, pool_start - len(rom))
                if pad:
                    rom.extend(b"\xFF" * pad)
                rom.extend(b"\xFF" * total_reloc_bytes)

            if pool_start is None:
                for item in reloc_items:
                    # Fallback seguro: se não houver espaço para repoint,
                    # tenta reformular para caber in-place sem overflow.
                    _plim = item.get("payload_limit", 0)
                    _term = item.get("term", b"")
                    _entry = item["entry"]
                    _fit = self._fit_ascii_reformulation(
                        text=item.get("sanitized", ""),
                        orig_text=item.get("orig_text", ""),
                        payload_limit=_plim,
                        term=_term,
                        tokens=item.get("tokens", []) or [],
                        allow_compact=True,
                        allow_hard_trim=True,
                    )
                    if _fit:
                        charset_stats["ascii_fallback_chars"] += int(_fit.get("fallback_chars", 0))
                        fits_items.append(
                            {
                                "key": item["key"],
                                "entry": _entry,
                                "encoded": _fit["encoded_with_term"],
                                "final_text": _fit.get("sanitized", ""),
                                "truncated": bool(_fit.get("hard_trim")),
                                "reformulated": bool(_fit.get("reformulated")),
                                "wrapped": str(_fit.get("strategy", "")).startswith("WRAP"),
                                "strategy": _fit.get("strategy", "REFORM"),
                            }
                        )
                        continue
                    not_applied.append({"key": item["key"], "reason": "repoint_failed_no_space"})
                    stats["BLOCKED"] += 1
                    stats["BLOCKED_NO_SPACE"] += 1
                    items_report.append(
                        {"key": item["key"], "action": "NOT_APPLIED", "reason": "repoint_failed_no_space"}
                    )
            else:
                cursor = pool_start
                for item in reloc_items:
                    entry = item["entry"]
                    cursor = self._align(cursor, alignment)
                    new_offset = cursor

                    # valida ponteiros
                    refs_for_entry, rejected_refs = self._filter_pointer_refs_for_safety(
                        list(entry.pointer_refs or []),
                        protected_pointer_ranges,
                    )
                    if rejected_refs > 0:
                        stats["PTR_REF_REJECTED_TEXT_OVERLAP"] = int(
                            stats.get("PTR_REF_REJECTED_TEXT_OVERLAP", 0)
                        ) + int(rejected_refs)
                    if not refs_for_entry:
                        discovered_refs = self._find_pointer_refs_for_target(
                            rom_bytes=bytes(rom[: len(rom_bytes)]),
                            old_offset=int(entry.offset),
                            new_offset=int(new_offset),
                            max_refs=512,
                        )
                        discovered_refs, discovered_rejected = self._filter_pointer_refs_for_safety(
                            discovered_refs,
                            protected_pointer_ranges,
                        )
                        if discovered_rejected > 0:
                            stats["PTR_REF_REJECTED_TEXT_OVERLAP"] = int(
                                stats.get("PTR_REF_REJECTED_TEXT_OVERLAP", 0)
                            ) + int(discovered_rejected)
                        if discovered_refs:
                            refs_for_entry = discovered_refs
                            entry.pointer_refs = discovered_refs
                            entry.pointer_offsets = [
                                int(r.get("ptr_offset", -1))
                                for r in discovered_refs
                                if self._parse_optional_int_value(r.get("ptr_offset")) is not None
                            ]
                            entry.has_pointer = True
                            stats["PTR_DISCOVERED_RUNTIME"] = int(
                                stats.get("PTR_DISCOVERED_RUNTIME", 0)
                            ) + 1
                    pointer_updates: List[Tuple[Dict[str, Any], int]] = []
                    valid = True
                    for ref in refs_for_entry:
                        value = self._calc_pointer_value(new_offset, ref)
                        if value is None:
                            valid = False
                            break
                        ptr_size = int(ref.get("ptr_size", 2))
                        if value >= (1 << (ptr_size * 8)):
                            valid = False
                            break
                        pointer_updates.append((ref, value))

                    if not valid or not pointer_updates:
                        # Fallback seguro: ponteiro inválido/estourado tenta caber in-place.
                        _plim = item.get("payload_limit", 0)
                        _term = item.get("term", b"")
                        _fit = self._fit_ascii_reformulation(
                            text=item.get("sanitized", ""),
                            orig_text=item.get("orig_text", ""),
                            payload_limit=_plim,
                            term=_term,
                            tokens=item.get("tokens", []) or [],
                            allow_compact=True,
                            allow_hard_trim=True,
                        )
                        if _fit:
                            charset_stats["ascii_fallback_chars"] += int(_fit.get("fallback_chars", 0))
                            fits_items.append(
                                {
                                    "key": item["key"],
                                    "entry": entry,
                                    "encoded": _fit["encoded_with_term"],
                                    "final_text": _fit.get("sanitized", ""),
                                    "truncated": bool(_fit.get("hard_trim")),
                                    "reformulated": bool(_fit.get("reformulated")),
                                    "wrapped": str(_fit.get("strategy", "")).startswith("WRAP"),
                                    "strategy": _fit.get("strategy", "REFORM"),
                                }
                            )
                            continue
                        reason = "no_pointer_sources" if not entry.pointer_refs else "pointer_overflow_or_missing"
                        not_applied.append({"key": item["key"], "reason": reason})
                        stats["BLOCKED"] += 1
                        items_report.append(
                            {"key": item["key"], "action": "NOT_APPLIED", "reason": reason}
                        )
                        continue

                    # escreve texto no pool
                    encoded = item["encoded"]
                    rom[new_offset : new_offset + len(encoded)] = encoded

                    # atualiza ponteiros
                    updated_ptrs = []
                    ok_ptrs = True
                    for ref, value in pointer_updates:
                        if not self._write_pointer_value(rom, ref, value):
                            ok_ptrs = False
                            break
                        updated_ptrs.append(ref.get("ptr_offset"))

                    if not ok_ptrs:
                        # Fallback seguro: falha de escrita de ponteiro tenta caber in-place.
                        _plim = item.get("payload_limit", 0)
                        _term = item.get("term", b"")
                        _fit = self._fit_ascii_reformulation(
                            text=item.get("sanitized", ""),
                            orig_text=item.get("orig_text", ""),
                            payload_limit=_plim,
                            term=_term,
                            tokens=item.get("tokens", []) or [],
                            allow_compact=True,
                            allow_hard_trim=True,
                        )
                        if _fit:
                            charset_stats["ascii_fallback_chars"] += int(_fit.get("fallback_chars", 0))
                            fits_items.append(
                                {
                                    "key": item["key"],
                                    "entry": entry,
                                    "encoded": _fit["encoded_with_term"],
                                    "final_text": _fit.get("sanitized", ""),
                                    "truncated": bool(_fit.get("hard_trim")),
                                    "reformulated": bool(_fit.get("reformulated")),
                                    "wrapped": str(_fit.get("strategy", "")).startswith("WRAP"),
                                    "strategy": _fit.get("strategy", "REFORM"),
                                }
                            )
                            continue
                        not_applied.append({
                            "key": item["key"],
                            "reason": "pointer_write_failed",
                        })
                        stats["BLOCKED"] += 1
                        items_report.append({
                            "key": item["key"],
                            "action": "NOT_APPLIED",
                            "reason": "pointer_write_failed",
                        })
                        continue

                    stats["REPOINT"] += 1
                    final_text = item.get("final_text", item.get("sanitized", ""))
                    if isinstance(final_text, str) and final_text.strip():
                        prepared_translated[item["key"]] = final_text
                    meta_for_item = (
                        fallback_entries.get(str(item["key"]))
                        if isinstance(fallback_entries, dict)
                        else None
                    )
                    old_payload_len = int(
                        self._resolve_entry_payload_len(
                            entry,
                            meta_for_item if isinstance(meta_for_item, dict) else None,
                        )
                    )
                    old_total_len = int(old_payload_len + (1 if entry.terminator is not None else 0))
                    hidden_prefix_patch = pending_hidden_prefix_patches.get(str(item["key"]))
                    if hidden_prefix_patch:
                        self._apply_hidden_prefix_patch_slots(rom, hidden_prefix_patch)
                    relocated_items.append(
                        {
                            "key": item["key"],
                            "old_offset": entry.offset,
                            "new_offset": new_offset,
                            "old_len": old_total_len,
                            "final_len": len(encoded),
                            "text_preview": str(final_text or "")[:160],
                            "pointer_sources_updated": updated_ptrs,
                        }
                    )
                    items_report.append(
                        {"key": item["key"], "action": "REPOINT", "offset": entry.offset, "new_offset": new_offset,
                         "max_len": entry.max_len, "new_len": len(encoded), "truncated": False,
                         "terminator": entry.terminator, "pointer_offsets": updated_ptrs}
                    )
                    cursor += len(encoded)

                if relocated_items:
                    bytes_used = max(0, cursor - pool_start)
                    bytes_free = max(0, total_reloc_bytes - bytes_used)
                    rom_expanded = len(rom) > len(rom_bytes)
                    pool_info = {
                        "start_hex": f"0x{pool_start:X}",
                        "end_hex": f"0x{pool_start + total_reloc_bytes:X}",
                        "bytes_used": int(bytes_used),
                        "bytes_free": int(bytes_free),
                        "alignment": alignment,
                        "filler_byte": int(filler_byte) if filler_byte is not None else None,
                        "expanded": bool(rom_expanded),
                        "forbidden_ranges_count": int(len(relocation_forbidden_ranges)),
                        "free_space_strategy": "tail_ff00_guarded",
                    }
                else:
                    # Se não houve realocação efetiva, descarta expansão reservada.
                    if len(rom) > len(rom_bytes):
                        del rom[len(rom_bytes):]
                    pool_info = {}

        # Alguns fallbacks da etapa de realocação podem inserir novos itens em fits_items.
        if len(fits_items) > applied_fits:
            for item in fits_items[applied_fits:]:
                _apply_fit_item(item)
            applied_fits = len(fits_items)

        translation_input["relocation_requested_items"] = int(len(reloc_items))
        translation_input["relocation_applied_items"] = int(len(relocated_items))
        translation_input["relocation_forbidden_ranges_count"] = int(len(relocation_forbidden_ranges))
        translation_input["relocation_alignment"] = int(alignment)
        if pool_info:
            translation_input["relocation_pool"] = dict(pool_info)
        if int(stats.get("BLOCKED_NO_SPACE", 0)) > 0:
            no_space_warn = (
                "CRITICAL: pool de realocação sem espaço suficiente; "
                "alguns textos ficaram bloqueados após tentativa de abreviação."
            )
            guardrail_warnings.append(no_space_warn)
            translation_input["guardrail_warnings"] = list(guardrail_warnings)
            translation_input["guardrail_warning_count"] = int(len(guardrail_warnings))
            stats["GUARDRAIL_WARN"] = int(len(guardrail_warnings))

        # 4) Blocos comprimidos (decompress -> patch -> recompress -> round-trip)
        if strict_crc_safe_mode:
            compressed_block_reinsertion = {
                "enabled": False,
                "candidates": 0,
                "blocks_total": 0,
                "blocks_applied": 0,
                "blocks_relocated": 0,
                "pointer_updates": 0,
                "inserted_items": 0,
                "truncated_items": 0,
                "blocked_items": 0,
                "roundtrip_baseline_fail_blocks": 0,
                "roundtrip_fail_blocks": 0,
                "unsupported_algorithm_blocks": 0,
                "examples": {"applied": [], "blocked": []},
                "limitations": ["disabled_by_strict_crc_safe_mode_de9f8517"],
            }
        else:
            compressed_block_reinsertion = self._apply_compressed_block_translations(
                rom=rom,
                translated=prepared_translated,
                fallback_entries=fallback_entries,
                stats=stats,
                items_report=items_report,
                not_applied=not_applied,
                charset_stats=charset_stats,
            )
        translation_input["compressed_block_reinsertion"] = {
            "enabled": bool(compressed_block_reinsertion.get("enabled", False)),
            "blocks_total": int(compressed_block_reinsertion.get("blocks_total", 0)),
            "blocks_applied": int(compressed_block_reinsertion.get("blocks_applied", 0)),
            "blocks_relocated": int(compressed_block_reinsertion.get("blocks_relocated", 0)),
            "candidates": int(compressed_block_reinsertion.get("candidates", 0)),
            "inserted_items": int(compressed_block_reinsertion.get("inserted_items", 0)),
            "truncated_items": int(compressed_block_reinsertion.get("truncated_items", 0)),
            "blocked_items": int(compressed_block_reinsertion.get("blocked_items", 0)),
            "roundtrip_baseline_fail_blocks": int(
                compressed_block_reinsertion.get("roundtrip_baseline_fail_blocks", 0)
            ),
            "roundtrip_fail_blocks": int(compressed_block_reinsertion.get("roundtrip_fail_blocks", 0)),
            "unsupported_algorithm_blocks": int(
                compressed_block_reinsertion.get("unsupported_algorithm_blocks", 0)
            ),
        }

        # 5) Modo seguro obrigatório: nenhuma escrita pode tocar bytes protegidos.
        protected_integrity_summary = self._enforce_protected_regions_integrity(
            rom=rom,
            original_rom=rom_bytes,
            protected_regions=protected_regions,
            protected_backup=protected_backup,
            items_report=items_report,
            not_applied=not_applied,
            stats=stats,
            fallback_entries=fallback_entries,
        )
        translation_input["protected_integrity"] = dict(protected_integrity_summary)
        translation_input["protected_changed_bytes"] = int(
            protected_integrity_summary.get("changed_protected_bytes", 0)
        )
        translation_input["protected_reverted_blocks"] = int(
            protected_integrity_summary.get("reverted_blocks", 0)
        )
        translation_input["protected_reverted_bytes"] = int(
            protected_integrity_summary.get("reverted_bytes", 0)
        )
        translation_input["protected_remaining_changed_bytes"] = int(
            protected_integrity_summary.get("remaining_changed_bytes", 0)
        )
        safe_logs = list(protected_integrity_summary.get("logs", []) or [])
        if safe_logs:
            for safe_msg in safe_logs[:8]:
                guardrail_warnings.append(str(safe_msg))
            translation_input["guardrail_warnings"] = list(guardrail_warnings)
            translation_input["guardrail_warning_count"] = int(len(guardrail_warnings))
            stats["GUARDRAIL_WARN"] = int(len(guardrail_warnings))

        ui_success_actions = {
            "OK",
            "FORCED",
            "REFORM",
            "WRAP",
            "SHORT",
            "REPOINT",
            "DTE",
            "CMP_OK",
            "CMP_REPOINT",
            "CMP_REPOINT_WRAP",
            "CMP_REPOINT_SHORT",
        }
        ui_last_event_by_key: Dict[str, Dict[str, Any]] = {}
        for row in items_report:
            if not isinstance(row, dict):
                continue
            row_key = str(row.get("key", ""))
            if not row_key or row_key not in ui_keys:
                continue
            ui_last_event_by_key[row_key] = row

        def _ui_meta_for_key(_key: str) -> Optional[Dict[str, Any]]:
            if isinstance(fallback_entries, dict):
                meta_obj = fallback_entries.get(str(_key))
                if isinstance(meta_obj, dict):
                    return meta_obj
            return None

        def _ui_range_for_key(_key: str) -> Optional[Tuple[int, int]]:
            meta_obj = _ui_meta_for_key(_key)
            entry_obj = self.mapping.get(str(_key))
            if entry_obj is None and isinstance(meta_obj, dict) and meta_obj:
                try:
                    entry_obj = self._mapentry_from_jsonl(str(_key), meta_obj)
                except Exception:
                    entry_obj = None
            if not isinstance(entry_obj, MapEntry):
                return None
            slot_len = int(
                self._resolve_entry_slot_total_len(
                    entry_obj,
                    meta_obj if isinstance(meta_obj, dict) else None,
                )
            )
            if slot_len <= 0:
                return None
            start = int(entry_obj.offset)
            end = int(entry_obj.offset) + int(slot_len)
            if end <= start:
                return None
            return (start, end)

        ui_success_ranges: List[Tuple[str, int, int]] = []
        for ui_k, last_event in ui_last_event_by_key.items():
            if not isinstance(last_event, dict):
                continue
            action = str(last_event.get("action", "") or "").upper()
            if action not in ui_success_actions:
                continue
            r = _ui_range_for_key(str(ui_k))
            if r:
                ui_success_ranges.append((str(ui_k), int(r[0]), int(r[1])))

        ui_reinserted_keys: set = set()
        ui_blocked_keys: set = set()
        ui_blocked_details = []
        for ui_key in sorted(ui_keys):
            last_event = ui_last_event_by_key.get(str(ui_key))
            if not isinstance(last_event, dict):
                meta_obj = _ui_meta_for_key(str(ui_key))
                meta_flags = set(self._normalized_review_flags(meta_obj))
                ui_range = _ui_range_for_key(str(ui_key))
                if "OVERLAP_DISCARDED" in meta_flags and ui_range:
                    alias_owner = None
                    for owner_key, owner_start, owner_end in ui_success_ranges:
                        if owner_key == str(ui_key):
                            continue
                        if owner_start <= int(ui_range[0]) and owner_end >= int(ui_range[1]):
                            alias_owner = owner_key
                            break
                    if alias_owner:
                        items_report.append(
                            {
                                "key": str(ui_key),
                                "action": "OK",
                                "offset": int(ui_range[0]),
                                "max_len": int(ui_range[1] - ui_range[0]),
                                "reason": f"overlap_alias_owner={alias_owner}",
                            }
                        )
                        ui_reinserted_keys.add(str(ui_key))
                        continue
                ui_blocked_keys.add(str(ui_key))
                ui_blocked_details.append(
                    {
                        "key": str(ui_key),
                        "offset": None,
                        "reason": "POINTER_INVALID",
                    }
                )
                continue
            action = str(last_event.get("action", "") or "").upper()
            if action in ui_success_actions:
                ui_reinserted_keys.add(str(ui_key))
                continue
            if action == "SKIP_OVERLAP":
                reason_text = str(last_event.get("reason", "") or "")
                if reason_text.startswith("overlap_with_key="):
                    owner_key = reason_text.split("=", 1)[1].strip()
                    if owner_key and owner_key in ui_keys:
                        # Alias de UI: a string efetiva foi aplicada no item dono do mesmo range.
                        ui_reinserted_keys.add(str(ui_key))
                        continue
            ui_blocked_keys.add(str(ui_key))
            ui_blocked_details.append(
                {
                    "key": str(ui_key),
                    "offset": last_event.get("offset"),
                    "reason": self._extract_ui_reason_from_item_report(last_event),
                }
            )

        ui_found_count = int(len(ui_keys))
        ui_extracted_count = int(len(ui_keys))
        ui_translated_count = int(
            sum(1 for k in ui_keys if str(prepared_translated.get(k, "") or "").strip())
        )
        ui_reinserted_count = int(len(ui_reinserted_keys))
        ui_blocked_count = int(len(ui_blocked_keys))

        stats["UI_ITEMS_FOUND"] = int(ui_found_count)
        stats["UI_ITEMS_EXTRACTED"] = int(ui_extracted_count)
        stats["UI_ITEMS_TRANSLATED"] = int(ui_translated_count)
        stats["UI_ITEMS_REINSERTED"] = int(ui_reinserted_count)
        stats["UI_ITEMS_BLOCKED"] = int(ui_blocked_count)

        # Métricas de aplicação real: separa bloqueio técnico de skip estrutural.
        final_action_by_key: Dict[str, Dict[str, Any]] = {}
        for row in items_report:
            if not isinstance(row, dict):
                continue
            row_key = str(row.get("key", "")).strip()
            if not row_key:
                continue
            final_action_by_key[row_key] = row

        # Ações consideradas aplicação bem-sucedida no pipeline principal.
        # Mantém alinhamento com o conjunto usado na apuração de UI para evitar
        # falso "BLOCKED_REAL" quando o item foi aplicado via atalho/compactação.
        success_actions = {
            "OK",
            "WRAP",
            "REFORM",
            "FORCED",
            "REPOINT",
            "SHORT",
            "DTE",
            "CMP_OK",
            "CMP_REPOINT",
            "CMP_REPOINT_WRAP",
            "CMP_REPOINT_SHORT",
        }
        structural_actions = {
            "SKIP_FRAGMENT",
            "SKIP_NONPLAUSIBLE",
            "SKIP_HARD_UNSAFE_SOURCE",
        }
        blocked_actions = {
            "NOT_APPLIED",
            "BLOCKED_INVALID",
            "BLOCKED_UNSAFE",
            "BLOCKED_NO_SPACE",
            "BLOCKED_NO_POINTER",
            "BLOCKED_PTR_MISMATCH",
            "BLOCKED_BANK0",
            "TRUNC",
            "SKIP_NO_MAPPING",
        }

        applied_keys = 0
        structural_skipped_keys = 0
        blocked_real_keys = 0
        unresolved_overlap_keys = 0
        resolved_overlap_keys = 0

        for row_key, row in final_action_by_key.items():
            action = str(row.get("action", "") or "").strip().upper()
            if action in success_actions:
                applied_keys += 1
                continue
            if action == "SKIP_OVERLAP":
                reason_text = str(row.get("reason", "") or "")
                owner_key = ""
                if reason_text.startswith("overlap_with_key="):
                    owner_key = reason_text.split("=", 1)[1].strip()
                owner_action = str(
                    (final_action_by_key.get(owner_key, {}) or {}).get("action", "") or ""
                ).strip().upper()
                if owner_key and owner_action in success_actions:
                    structural_skipped_keys += 1
                    resolved_overlap_keys += 1
                else:
                    blocked_real_keys += 1
                    unresolved_overlap_keys += 1
                continue
            if action in structural_actions:
                structural_skipped_keys += 1
                continue
            if action in blocked_actions or action.startswith("BLOCKED"):
                blocked_real_keys += 1
                continue
            blocked_real_keys += 1

        keys_total = int(len(final_action_by_key))
        effective_total_keys = max(0, keys_total - structural_skipped_keys)
        applied_percent_global = (
            (float(applied_keys) / float(keys_total)) * 100.0 if keys_total > 0 else 100.0
        )
        blocked_percent_global = (
            (float(blocked_real_keys) / float(keys_total)) * 100.0 if keys_total > 0 else 0.0
        )
        applied_percent_effective = (
            (float(applied_keys) / float(effective_total_keys)) * 100.0
            if effective_total_keys > 0
            else 100.0
        )
        blocked_percent_effective = (
            (float(blocked_real_keys) / float(effective_total_keys)) * 100.0
            if effective_total_keys > 0
            else 0.0
        )
        covered_with_overlap_keys = int(applied_keys + resolved_overlap_keys)
        covered_with_overlap_percent = (
            (float(covered_with_overlap_keys) / float(keys_total)) * 100.0
            if keys_total > 0
            else 100.0
        )
        application_metrics = {
            "keys_total": int(keys_total),
            "effective_total_keys": int(effective_total_keys),
            "applied_keys": int(applied_keys),
            "structural_skipped_keys": int(structural_skipped_keys),
            "blocked_real_keys": int(blocked_real_keys),
            "unresolved_overlap_keys": int(unresolved_overlap_keys),
            "resolved_overlap_keys": int(resolved_overlap_keys),
            "covered_with_overlap_keys": int(covered_with_overlap_keys),
            "applied_percent_global": round(applied_percent_global, 2),
            "blocked_percent_global": round(blocked_percent_global, 2),
            "applied_percent_effective": round(applied_percent_effective, 2),
            "blocked_percent_effective": round(blocked_percent_effective, 2),
            "covered_with_overlap_percent": round(covered_with_overlap_percent, 2),
        }
        stats["APPLIED_KEYS"] = int(applied_keys)
        stats["STRUCTURAL_SKIPPED"] = int(structural_skipped_keys)
        stats["BLOCKED_REAL"] = int(blocked_real_keys)
        stats["EFFECTIVE_TOTAL_KEYS"] = int(effective_total_keys)
        stats["UNRESOLVED_OVERLAP"] = int(unresolved_overlap_keys)
        stats["RESOLVED_OVERLAP"] = int(resolved_overlap_keys)
        stats["COVERED_WITH_OVERLAP_KEYS"] = int(covered_with_overlap_keys)
        stats["COVERED_WITH_OVERLAP_PERCENT"] = round(covered_with_overlap_percent, 2)

        if strict and (stats.get("TRUNC", 0) > 0 or stats.get("BLOCKED", 0) > 0):
            raise ReinsertionError(
                f"strict=True bloqueou a reinserção: TRUNC={stats.get('TRUNC', 0)} "
                f"BLOCKED={stats.get('BLOCKED', 0)}"
            )

        crc_tag = (self.mapping_crc32 or crc_before).upper()
        rom_size = len(rom)
        out_dir = rom_path.parent / "out"
        out_dir.mkdir(parents=True, exist_ok=True)

        out_suffix = rom_path.suffix if rom_path.suffix else ".sms"
        neutral_patched_path = out_dir / f"{crc_tag}_patched{out_suffix}"
        if output_rom_path is None:
            output_rom_path = neutral_patched_path
        output_rom_path = Path(output_rom_path)

        auto_diff_ranges_info = self._auto_generate_diff_ranges_from_mapping(
            mapping_path=mapping_path,
            rom_path=rom_path,
            crc_tag=crc_tag,
            rom_size=rom_size,
        )
        translation_input["auto_generate_diff_ranges"] = bool(
            (auto_diff_ranges_info or {}).get("enabled", False)
        )
        translation_input["auto_generate_diff_ranges_generated"] = bool(
            (auto_diff_ranges_info or {}).get("generated", False)
        )
        translation_input["auto_generate_diff_ranges_count"] = int(
            (auto_diff_ranges_info or {}).get("ranges_count", 0) or 0
        )
        translation_input["auto_generate_diff_ranges_written_paths"] = list(
            (auto_diff_ranges_info or {}).get("written_paths", []) or []
        )[:12]
        translation_input["auto_generate_diff_ranges_skipped_existing"] = int(
            len((auto_diff_ranges_info or {}).get("skipped_existing_paths", []) or [])
        )
        translation_input["auto_generate_diff_ranges_margin_start"] = int(
            (auto_diff_ranges_info or {}).get("margin_start", 0) or 0
        )
        translation_input["auto_generate_diff_ranges_margin_end"] = int(
            (auto_diff_ranges_info or {}).get("margin_end", 0) or 0
        )
        translation_input["auto_generate_diff_ranges_merge_gap"] = int(
            (auto_diff_ranges_info or {}).get("merge_gap", 0) or 0
        )
        translation_input["auto_generate_diff_ranges_error"] = str(
            (auto_diff_ranges_info or {}).get("error", "") or ""
        )

        # Allowed ranges (texto + pool + gráficos)
        allowed_ranges: List[Tuple[int, int]] = []
        for entry in self.mapping.values():
            meta_for_entry = (
                fallback_entries.get(str(entry.key))
                if isinstance(fallback_entries, dict)
                else None
            )
            size = int(
                self._resolve_entry_slot_total_len(
                    entry,
                    meta_for_entry if isinstance(meta_for_entry, dict) else None,
                )
            )
            if size <= 0:
                continue
            allowed_ranges.append((int(entry.offset), int(entry.offset) + size))
            for ref in entry.pointer_refs or []:
                try:
                    ptr_off = int(ref.get("ptr_offset", -1))
                    ptr_size = int(ref.get("ptr_size", 2))
                    if ptr_off >= 0 and ptr_size > 0:
                        allowed_ranges.append((ptr_off, ptr_off + ptr_size))
                except Exception:
                    continue
            for ptr_off in entry.pointer_offsets or []:
                try:
                    ptr_off = int(ptr_off)
                    allowed_ranges.append((ptr_off, ptr_off + 2))
                except Exception:
                    continue
        if pool_info:
            try:
                pool_start = int(str(pool_info.get("start_hex", "0x0")), 16)
                pool_end = int(str(pool_info.get("end_hex", "0x0")), 16)
                if pool_end > pool_start:
                    allowed_ranges.append((pool_start, pool_end))
            except Exception:
                pass
        if fallback_entries:
            for meta in fallback_entries.values():
                for rg in meta.get("gfx_ranges", []) or meta.get("graphics_ranges", []) or []:
                    try:
                        if isinstance(rg, str) and "-" in rg:
                            a, b = rg.split("-", 1)
                            start = int(a.strip(), 16)
                            end = int(b.strip(), 16)
                        else:
                            start = int(rg.get("start", 0))
                            end = int(rg.get("end", 0))
                        if end > start:
                            allowed_ranges.append((start, end))
                    except Exception:
                        continue
        for patch in pending_hidden_prefix_patches.values():
            if not isinstance(patch, dict):
                continue
            slots: List[int] = []
            for value in patch.get("slots", []) or []:
                parsed = self._parse_optional_int_value(value)
                if parsed is None:
                    continue
                slots.append(int(parsed))
            if slots:
                allowed_ranges.append((min(slots), max(slots) + 1))
        # Inclui alterações da etapa de glifos (pré-texto), quando presentes.
        if glyph_allowed_ranges:
            allowed_ranges.extend(glyph_allowed_ranges)

        external_allowed_ranges, external_allowed_source = self._load_external_allowed_ranges(
            mapping_path=mapping_path,
            rom_path=rom_path,
            crc_tag=crc_tag,
            rom_size=rom_size,
        )
        if external_allowed_ranges:
            allowed_ranges.extend(external_allowed_ranges)
        translation_input["glyph_allowed_ranges_count"] = int(len(glyph_allowed_ranges))
        translation_input["external_allowed_ranges_count"] = int(len(external_allowed_ranges))
        translation_input["external_allowed_ranges_source"] = external_allowed_source

        diff_ranges = self._compute_diff_ranges(rom_bytes, bytes(rom))
        diff_outside = [
            r for r in diff_ranges if not self._range_is_allowed(r["start"], r["end"], allowed_ranges)
        ]
        diff_blocked = bool(diff_outside)

        diff_payload = {
            "crc32": crc_tag,
            "rom_size": rom_size,
            "diff_ranges": diff_ranges,
            "outside_allowed": diff_outside,
            "allowed_ranges_count": len(allowed_ranges),
            "glyph_allowed_ranges_count": len(glyph_allowed_ranges),
            "external_allowed_ranges_count": len(external_allowed_ranges),
            "external_allowed_ranges_source": external_allowed_source,
        }
        diff_path = out_dir / f"{crc_tag}_diff_ranges.json"
        diff_path.write_text(json.dumps(diff_payload, indent=2, ensure_ascii=False), encoding="utf-8")

        # Backup da ROM original
        backup_path = None
        if create_backup and not dry_run and not diff_blocked:
            backup_path = make_backup(rom_path)

        # Escrita atômica do ROM modificado (somente se diff válido)
        if not dry_run and not diff_blocked:
            ensure_parent_dir(output_rom_path)
            atomic_write_bytes(output_rom_path, bytes(rom))
            if output_rom_path.resolve() != neutral_patched_path.resolve():
                atomic_write_bytes(neutral_patched_path, bytes(rom))

        crc_after, sha_after = compute_checksums(bytes(rom))

        # Copia outputs obrigatórios para out\{CRC32}_*
        def _copy_if_exists(src: Optional[Path], dst: Path):
            try:
                if src and src.exists():
                    shutil.copy2(src, dst)
            except Exception:
                pass

        pure_src = None
        if translated_path.suffix.lower() == ".jsonl":
            if translated_path.name.endswith("_translated.jsonl"):
                cand = translated_path.with_name(
                    translated_path.name.replace("_translated.jsonl", "_pure_text.jsonl")
                )
                if cand.exists():
                    pure_src = cand
            if pure_src is None:
                cand = translated_path.with_name(translated_path.name.replace(".jsonl", "_pure_text.jsonl"))
                if cand.exists():
                    pure_src = cand
            if pure_src is None:
                cand = translated_path.parent / f"{crc_tag}_pure_text.jsonl"
                if cand.exists():
                    pure_src = cand
        _copy_if_exists(pure_src, out_dir / f"{crc_tag}_pure_text.jsonl")
        _copy_if_exists(mapping_path, out_dir / f"{crc_tag}_reinsertion_mapping.json")

        file_tags: List[str] = []
        for tag in [crc_after.upper(), crc_before.upper(), crc_tag]:
            if tag and tag not in file_tags:
                file_tags.append(tag)

        runtime_entry_overrides: Dict[str, Dict[str, int]] = {}
        for item in items_report:
            if not isinstance(item, dict):
                continue
            key_raw = item.get("key")
            if key_raw is None:
                continue
            action = str(item.get("action", "") or "").upper()
            if action not in {
                "REPOINT",
                "CMP_REPOINT",
                "CMP_REPOINT_WRAP",
                "CMP_REPOINT_SHORT",
            }:
                continue
            new_off = self._parse_optional_int_value(item.get("new_offset"))
            if new_off is None:
                continue
            new_len = self._parse_optional_int_value(item.get("new_len"))
            runtime_entry_overrides[str(key_raw)] = {
                "offset": int(new_off),
                "max_len": int(new_len) if new_len is not None and int(new_len) > 0 else 0,
            }

        not_applied_keys_for_issue = {
            str(item.get("key"))
            for item in (not_applied or [])
            if isinstance(item, dict) and item.get("key") is not None
        }
        issue_restrict_keys = {str(k) for k in prepared_translated.keys()}
        if not_applied_keys_for_issue:
            issue_restrict_keys = {
                key for key in issue_restrict_keys if key not in not_applied_keys_for_issue
            }

        issue_index_after = self._build_incremental_issue_index(
            translated=prepared_translated,
            fallback_entries=fallback_entries,
            rom_bytes=bytes(rom),
            restrict_keys=issue_restrict_keys,
            runtime_entry_overrides=runtime_entry_overrides,
        )
        display_trace_bundle = self._build_display_trace_artifacts(
            ordered_keys=ordered_keys,
            prepared_translated=prepared_translated,
            items_report=items_report,
            fallback_entries=fallback_entries,
            issue_index_after=issue_index_after,
            translation_quality=translation_quality,
            rom_before_bytes=rom_bytes,
            runtime_crc32=crc_before.upper(),
            runtime_size=int(rom_size),
        )
        displayed_trace_rows = display_trace_bundle.get("trace_rows", []) or []
        missing_displayed_rows = display_trace_bundle.get("missing_rows", []) or []
        coverage_summary = display_trace_bundle.get("coverage_summary", {}) or {}

        display_trace_meta = {
            "type": "meta",
            "schema": "displayed_text_trace.v1",
            "rom_crc32": crc_before.upper(),
            "rom_size": int(rom_size),
            "items_total": int(len(displayed_trace_rows)),
        }
        missing_display_meta = {
            "type": "meta",
            "schema": "missing_displayed_text.v1",
            "rom_crc32": crc_before.upper(),
            "rom_size": int(rom_size),
            "items_total": int(len(missing_displayed_rows)),
        }
        displayed_trace_paths = self._write_jsonl_artifact_aliases(
            out_dir=out_dir,
            file_tags=file_tags,
            suffix_name="displayed_text_trace",
            rows=displayed_trace_rows,
            meta_record=display_trace_meta,
        )
        missing_displayed_paths = self._write_jsonl_artifact_aliases(
            out_dir=out_dir,
            file_tags=file_tags,
            suffix_name="missing_displayed_text",
            rows=missing_displayed_rows,
            meta_record=missing_display_meta,
        )
        coverage_summary_paths = self._write_json_artifact_aliases(
            out_dir=out_dir,
            file_tags=file_tags,
            suffix_name="coverage_summary",
            data=coverage_summary,
        )
        displayed_trace_primary = displayed_trace_paths.get(crc_after.upper())
        missing_displayed_primary = missing_displayed_paths.get(crc_after.upper())
        coverage_summary_primary = coverage_summary_paths.get(crc_after.upper())

        trunc_examples = [it for it in items_report if it.get("truncated")][:10]
        blocked_examples = [it for it in items_report if str(it.get("action", "")).startswith("NOT_")][:10]
        audit_items = 0
        audit_unknown_bytes_total = 0
        audit_roundtrip_fail_count = 0
        audit_overlap_items = 0
        reinsertion_safe_count = 0
        if isinstance(fallback_entries, dict):
            for meta in fallback_entries.values():
                if not isinstance(meta, dict):
                    continue
                audit_items += 1
                if bool(meta.get("reinsertion_safe", False)):
                    reinsertion_safe_count += 1
                audit_unknown_bytes_total += int(
                    self._parse_optional_int_value(meta.get("unknown_bytes_count")) or 0
                )
                if meta.get("audit_roundtrip_ok") is False:
                    audit_roundtrip_fail_count += 1
                overlap_flags = set(self._normalized_review_flags(meta))
                if any("OVERLAP" in str(flag).upper() for flag in overlap_flags):
                    audit_overlap_items += 1
        evidence = {
            "AUDIT_ITEMS": int(audit_items),
            "AUDIT_UNKNOWN_BYTES_TOTAL": int(audit_unknown_bytes_total),
            "AUDIT_ROUNDTRIP_FAIL_COUNT": int(audit_roundtrip_fail_count),
            "AUDIT_OVERLAP_ITEMS": int(audit_overlap_items),
            "REINSERTION_SAFE_COUNT": int(reinsertion_safe_count),
            "UI_ITEMS_FOUND": int(ui_found_count),
            "UI_ITEMS_EXTRACTED": int(ui_extracted_count),
            "UI_ITEMS_TRANSLATED": int(ui_translated_count),
            "UI_ITEMS_REINSERTED": int(ui_reinserted_count),
            "UI_ITEMS_BLOCKED": int(ui_blocked_count),
            "UI_ITEMS_BLOCKED_DETAILS": list(ui_blocked_details),
            "displayed_trace_skip_displayed_count": int(
                (coverage_summary or {}).get("displayed_trace_skip_displayed_count", 0)
            ),
            "displayed_trace_english_residual_count": int(
                (coverage_summary or {}).get("displayed_trace_english_residual_count", 0)
            ),
            "displayed_trace_same_as_source_phrase_count": int(
                (coverage_summary or {}).get("displayed_trace_same_as_source_phrase_count", 0)
            ),
            "not_translated_count": coverage.get("untranslated_same_as_source", 0),
            "same_as_source_phrase_count": coverage.get("untranslated_same_as_source", 0),
            "same_as_source_raw_count": coverage.get("same_as_source_raw", 0),
            "same_as_source_non_actionable_count": coverage.get("same_as_source_non_actionable", 0),
            "truncated_count": stats.get("TRUNC", 0),
            "applied_global_percent": float(application_metrics.get("applied_percent_global", 0.0)),
            "applied_effective_percent": float(application_metrics.get("applied_percent_effective", 0.0)),
            "blocked_real_count": int(application_metrics.get("blocked_real_keys", 0)),
            "structural_skipped_count": int(application_metrics.get("structural_skipped_keys", 0)),
            "non_ptbr_suspect_count": translation_quality.get("non_ptbr_suspect", 0),
            "english_likely_count": translation_quality.get("english_likely", 0),
            "unchanged_equal_src_count": issue_index_after.get("counts", {}).get("unchanged_equal_src", 0),
            "suspicious_non_pt_count": issue_index_after.get("counts", {}).get("suspicious_non_pt", 0),
            "rom_vs_translated_mismatch_count": issue_index_after.get("counts", {}).get("rom_vs_translated_mismatch", 0),
            "placeholder_fail_count": issue_index_after.get("counts", {}).get("placeholder_fail", 0),
            "terminator_missing_count": issue_index_after.get("counts", {}).get("terminator_missing", 0),
            "examples": {
                "untranslated_same_as_source": coverage.get("samples", {}).get("untranslated_same_as_source", []),
                "same_as_source_non_actionable": coverage.get("samples", {}).get("same_as_source_non_actionable", []),
                "truncated": trunc_examples,
                "blocked": blocked_examples,
                "non_ptbr_suspect": translation_quality.get("examples", {}).get("non_ptbr_suspect", []),
                "unchanged_equal_src": issue_index_after.get("examples", {}).get("unchanged_equal_src", []),
                "suspicious_non_pt": issue_index_after.get("examples", {}).get("suspicious_non_pt", []),
                "rom_vs_translated_mismatch": issue_index_after.get("examples", {}).get("rom_vs_translated_mismatch", []),
                "placeholder_fail": issue_index_after.get("examples", {}).get("placeholder_fail", []),
                "terminator_missing": issue_index_after.get("examples", {}).get("terminator_missing", []),
            },
        }
        delta_incremental = None
        if isinstance(delta_context, dict) and delta_context:
            before_index = delta_context.get("before_issue_index")
            if not isinstance(before_index, dict):
                before_index = self._empty_issue_index()
            reported_before_index = delta_context.get("reported_before_issue_index")
            if not isinstance(reported_before_index, dict):
                reported_before_index = self._empty_issue_index()
            before_counts = {}
            reported_before_counts = {}
            after_counts = {}
            improvement = {}
            for cat in self.DELTA_ISSUE_CATEGORIES:
                b_count = int((before_index.get("counts", {}) or {}).get(cat, 0))
                rb_count = int((reported_before_index.get("counts", {}) or {}).get(cat, 0))
                a_count = int((issue_index_after.get("counts", {}) or {}).get(cat, 0))
                before_counts[cat] = b_count
                reported_before_counts[cat] = rb_count
                after_counts[cat] = a_count
                improvement[cat] = b_count - a_count
            delta_incremental = {
                "enabled": True,
                "delta_path": delta_context.get("delta_path"),
                "source_path": delta_context.get("source_path"),
                "problem_keys_total": int(delta_context.get("problem_keys_total", len(prepared_translated))),
                "artifact_paths": delta_context.get("artifact_paths", {}),
                "categories": list(self.DELTA_ISSUE_CATEGORIES),
                "before": {
                    "counts": before_counts,
                    "examples": before_index.get("examples", {}),
                },
                "reported_before": {
                    "counts": reported_before_counts,
                    "examples": reported_before_index.get("examples", {}),
                },
                "after": {
                    "counts": after_counts,
                    "examples": issue_index_after.get("examples", {}),
                },
                "improvement": improvement,
                "strict_validation": bool(strict),
                "truncation_count": int(stats.get("TRUNC", 0)),
                "blocked_count": int(stats.get("BLOCKED", 0)),
                "criteria": {
                    "reduced_unchanged_equal_src": after_counts.get("unchanged_equal_src", 0)
                    <= before_counts.get("unchanged_equal_src", 0),
                    "reduced_suspicious_non_pt": after_counts.get("suspicious_non_pt", 0)
                    <= before_counts.get("suspicious_non_pt", 0),
                    "no_truncation": int(stats.get("TRUNC", 0)) == 0,
                    "no_blocked": int(stats.get("BLOCKED", 0)) == 0,
                },
            }
        limitations: List[str] = []
        comp_mode = str(
            compression_policy.get("mode", "")
            if isinstance(compression_policy, dict)
            else ""
        ).strip().lower()
        comp_notes = str(
            compression_policy.get("notes", "")
            if isinstance(compression_policy, dict)
            else ""
        ).strip()
        if comp_mode in ("mixed", "proprietary", "external"):
            limitations.append(
                "Perfil de engenharia indica script parcialmente comprimido/proprietário; "
                "cobertura completa depende de codec específico por jogo."
            )
        if comp_notes:
            limitations.append(f"Compressao/perfil: {comp_notes}")
        if int(compressed_block_reinsertion.get("candidates", 0)) > 0 and int(
            compressed_block_reinsertion.get("blocks_applied", 0)
        ) == 0:
            limitations.append(
                "Foram detectados textos em blocos comprimidos, mas nenhum bloco foi aplicado."
            )
        if int(compressed_block_reinsertion.get("roundtrip_fail_blocks", 0)) > 0:
            limitations.append(
                f"Falha de round-trip em {compressed_block_reinsertion.get('roundtrip_fail_blocks', 0)} blocos comprimidos."
            )
        if int(compressed_block_reinsertion.get("unsupported_algorithm_blocks", 0)) > 0:
            limitations.append(
                f"Existem {compressed_block_reinsertion.get('unsupported_algorithm_blocks', 0)} blocos comprimidos com algoritmo não suportado."
            )
        if int(compressed_block_reinsertion.get("blocked_items", 0)) > 0:
            limitations.append(
                f"{compressed_block_reinsertion.get('blocked_items', 0)} itens comprimidos foram bloqueados na reinserção."
            )
        if stats.get("PTR_FROM_META", 0) == 0 and stats.get("REPOINT", 0) == 0:
            limitations.append("Nenhum ponteiro válido foi aplicado; realocação não pôde ser usada.")
        if stats.get("TRUNC", 0) > 0:
            limitations.append(
                f"Ainda existem {stats.get('TRUNC', 0)} truncamentos após abreviação/reformulação."
            )
        if evidence.get("not_translated_count", 0) > 0:
            limitations.append(
                f"Ainda existem {evidence.get('not_translated_count', 0)} linhas não traduzidas acionáveis."
            )
        if translation_quality.get("non_ptbr_suspect", 0) > 0:
            limitations.append(
                f"Foram detectadas {translation_quality.get('non_ptbr_suspect', 0)} linhas suspeitas de não estar em PT-BR."
            )
        if issue_index_after.get("counts", {}).get("rom_vs_translated_mismatch", 0) > 0:
            limitations.append(
                f"Persistem {issue_index_after.get('counts', {}).get('rom_vs_translated_mismatch', 0)} divergências ROM vs texto traduzido."
            )
        if issue_index_after.get("counts", {}).get("placeholder_fail", 0) > 0:
            limitations.append(
                f"Persistem {issue_index_after.get('counts', {}).get('placeholder_fail', 0)} falhas de placeholder/token."
            )
        if issue_index_after.get("counts", {}).get("terminator_missing", 0) > 0:
            limitations.append(
                f"Persistem {issue_index_after.get('counts', {}).get('terminator_missing', 0)} casos de terminador ausente."
            )
        if not ordering_check.get("seq_consistent", True):
            limitations.append("Seq inconsistente entre entradas traduzidas e mapeamento.")
        if coverage_check.get("count_offsets_below_0x10000", 0) == 0:
            limitations.append(
                "intro possivelmente não extraído/mapeado (count_offsets_below_0x10000=0)."
            )
        if delta_incremental:
            criteria = delta_incremental.get("criteria", {}) or {}
            failed_delta = [name for name, ok in criteria.items() if not bool(ok)]
            if failed_delta:
                limitations.append(
                    "Reinserção delta não cumpriu totalmente os critérios: "
                    + ", ".join(failed_delta)
                )

        qa_final = None
        qa_artifacts: Dict[str, Any] = {}
        if evaluate_reinsertion_qa and write_qa_artifacts:
            try:
                require_manual_emulator = (
                    os.environ.get("NEUROROM_REQUIRE_MANUAL_EMULATOR", "0") == "1"
                )
                qa_final = evaluate_reinsertion_qa(
                    console="SMS",
                    rom_crc32=crc_before.upper(),
                    rom_size=rom_size,
                    stats=stats,
                    evidence=evidence,
                    checks={
                        "input_match": bool(
                            input_match_check.get("rom_crc32_match", False)
                            and input_match_check.get("rom_size_match", False)
                        ),
                        "ordering": bool(
                            ordering_check.get("is_sorted_by_offset", False)
                            and ordering_check.get("seq_consistent", False)
                        ),
                        "emulator_smoke": None,
                    },
                    limitations=limitations,
                    compression_policy=(
                        compression_policy if isinstance(compression_policy, dict) else {}
                    ),
                    translation_input=translation_input,
                    require_manual_emulator=require_manual_emulator,
                )
                qa_by_tag: Dict[str, Dict[str, str]] = {}
                for tag in file_tags:
                    q_json, q_txt = write_qa_artifacts(out_dir, tag, qa_final)
                    qa_by_tag[str(tag)] = {
                        "json": str(q_json),
                        "txt": str(q_txt),
                    }
                qa_artifacts = {
                    "by_tag": qa_by_tag,
                    "json": qa_by_tag.get(crc_after.upper(), {}).get("json"),
                    "txt": qa_by_tag.get(crc_after.upper(), {}).get("txt"),
                }
            except Exception as exc:
                limitations.append(f"Falha ao gerar QA final automatizado: {exc}")

        qa_gate_result: Dict[str, Any] = {
            "pass": True,
            "stage": "post_reinsertion",
            "reason": "QA_GATE_NOT_RUN",
        }
        runtime_coverage_result: Dict[str, Any] = {
            "provided": False,
            "pass": True,
            "reason": "RUNTIME_COVERAGE_NOT_RUN",
        }
        verified_100 = False
        try:
            pure_for_qa = pure_src if (pure_src and pure_src.exists()) else None
            if pure_for_qa is None:
                pure_candidate = out_dir / f"{crc_tag}_pure_text.jsonl"
                if pure_candidate.exists():
                    pure_for_qa = pure_candidate

            if (
                run_qa_gate_runtime is not None
                and pure_for_qa is not None
                and translated_path.suffix.lower() == ".jsonl"
            ):
                qa_gate_result = run_qa_gate_runtime(
                    pure_jsonl_path=str(pure_for_qa),
                    translated_jsonl_path=str(translated_path),
                    mapping_json_path=(str(mapping_path) if mapping_path else None),
                    report_json_path=None,
                    proof_json_path=None,
                    tbl_path=None,
                    stage="post_reinsertion",
                    reported_counters={
                        "blocked": int(stats.get("BLOCKED", 0) or 0),
                        "ui_items_blocked": int(ui_blocked_count),
                        "terminator_missing_count": int(
                            (issue_index_after.get("counts", {}) or {}).get("terminator_missing", 0)
                            or 0
                        ),
                    },
                )
                if not bool(qa_gate_result.get("pass", False)):
                    limitations.append(
                        "QA_GATE falhou: "
                        + ", ".join(qa_gate_result.get("failed_checks", []) or [])
                    )

            runtime_cov_enabled = os.environ.get("NEUROROM_RUNTIME_COVERAGE_ENABLE", "1") != "0"
            runtime_evidence_path = str(
                os.environ.get("NEUROROM_RUNTIME_EVIDENCE_PATH", "") or ""
            ).strip()
            if (
                runtime_cov_enabled
                and run_runtime_coverage_runtime is not None
                and pure_for_qa is not None
                and translated_path.suffix.lower() == ".jsonl"
            ):
                if not runtime_evidence_path and discover_runtime_evidence_path_runtime is not None:
                    runtime_evidence_path = (
                        discover_runtime_evidence_path_runtime(
                            rom_crc32=crc_before.upper(),
                            hint_paths=[
                                str(translated_path),
                                str(pure_for_qa),
                                str(mapping_path) if mapping_path else "",
                                str(out_dir),
                            ],
                        )
                        or ""
                    )
                runtime_coverage_result = run_runtime_coverage_runtime(
                    pure_jsonl_path=str(pure_for_qa),
                    translated_jsonl_path=str(translated_path),
                    mapping_json_path=(str(mapping_path) if mapping_path else None),
                    runtime_evidence_path=(runtime_evidence_path or None),
                    rom_crc32=crc_before.upper(),
                    rom_size=int(rom_size),
                )
                if bool(runtime_coverage_result.get("provided", False)) and not bool(
                    runtime_coverage_result.get("pass", False)
                ):
                    limitations.append(
                        "RUNTIME_COVERAGE falhou: "
                        f"reason={runtime_coverage_result.get('reason', '')} "
                        f"unmapped={runtime_coverage_result.get('runtime_unmapped_total', 0)} "
                        f"untranslated={runtime_coverage_result.get('runtime_untranslated_total', 0)}"
                    )

            verified_100 = bool(
                bool(qa_gate_result.get("pass", False))
                and (
                    not bool(runtime_coverage_result.get("provided", False))
                    or bool(runtime_coverage_result.get("pass", False))
                )
            )
        except Exception as qa_exc:
            limitations.append(f"Falha ao executar QA_GATE/RUNTIME_COVERAGE: {qa_exc}")

        layout_adjusted_examples = [
            {
                "key": row.get("key"),
                "action": row.get("action"),
                "strategy": row.get("strategy"),
            }
            for row in items_report
            if str(row.get("action", "")).upper() in {"WRAP", "REFORM", "SHORT"}
            or any(
                tag in str(row.get("strategy", "")).upper()
                for tag in ("WRAP", "SHORT", "ABBREV", "COMPACT", "INITIALS")
            )
        ]
        layout_adjusted = {
            "adjusted_count": int(stats.get("LAYOUT_ADJUSTED", 0)),
            "short_style_count": int(stats.get("LAYOUT_SHORT_STYLE", 0)),
            "examples": layout_adjusted_examples[:20],
        }
        relocated_texts = [
            {
                "id": row.get("key"),
                "old_offset": row.get("old_offset"),
                "new_offset": row.get("new_offset"),
                "old_len": row.get("old_len"),
                "new_len": row.get("final_len"),
                "pointer_updates": row.get("pointer_sources_updated", []),
                "preview": row.get("text_preview", ""),
            }
            for row in (relocated_items or [])
        ]

        # proof.json (evidências auditáveis)
        proof = {
            "relocated_pool": pool_info if pool_info else None,
            "relocated_items": relocated_items,
            "relocated_texts": relocated_texts,
            "not_applied": not_applied,
            "AUDIT_ITEMS": int(audit_items),
            "AUDIT_UNKNOWN_BYTES_TOTAL": int(audit_unknown_bytes_total),
            "AUDIT_ROUNDTRIP_FAIL_COUNT": int(audit_roundtrip_fail_count),
            "AUDIT_OVERLAP_ITEMS": int(audit_overlap_items),
            "REINSERTION_SAFE_COUNT": int(reinsertion_safe_count),
            "UI_ITEMS_FOUND": int(ui_found_count),
            "UI_ITEMS_EXTRACTED": int(ui_extracted_count),
            "UI_ITEMS_TRANSLATED": int(ui_translated_count),
            "UI_ITEMS_REINSERTED": int(ui_reinserted_count),
            "UI_ITEMS_BLOCKED": int(ui_blocked_count),
            "ui_blocked_items": list(ui_blocked_details),
            "ITEMS_TOTAL": int(audit_items),
            "coverage": coverage,
            "displayed_text_trace": {
                "items_total": int(len(displayed_trace_rows)),
                "path": displayed_trace_primary,
                "paths_by_tag": displayed_trace_paths,
            },
            "missing_displayed_text": {
                "items_total": int(len(missing_displayed_rows)),
                "path": missing_displayed_primary,
                "paths_by_tag": missing_displayed_paths,
            },
            "coverage_summary": coverage_summary,
            "coverage_summary_path": coverage_summary_primary,
            "coverage_summary_paths_by_tag": coverage_summary_paths,
            "translation_input": translation_input,
            "guardrail_warnings": list(guardrail_warnings),
            "input_match_check": input_match_check,
            "ordering_check": ordering_check,
            "coverage_check": coverage_check,
            "strict_ptbr": strict_ptbr_info,
            "id_override": id_override_info,
            "game_engineering": {
                "profile": game_engineering_info,
                "text_rewrites": int(self._game_engineering_text_changes),
            },
            "translation_quality": translation_quality,
            "issue_index": issue_index_after,
            "delta_incremental": delta_incremental,
            "compressed_block_reinsertion": compressed_block_reinsertion,
            "evidence": evidence,
            "limitations": limitations,
            "charset_stats": charset_stats,
            "charset_policy": charset_policy,
            "layout_adjusted": layout_adjusted,
            "glyph_injection": glyph_injection_report,
            "consolidated": {
                "glyphs_injected": int((glyph_injection_report or {}).get("injected_count", 0) or 0),
                "glyphs_base": int((glyph_injection_report or {}).get("injected_from_base_count", 0) or 0),
                "glyphs_verdana": int((glyph_injection_report or {}).get("injected_from_verdana_count", 0) or 0),
                "tilemaps_ignored_no_tbl": int(stats.get("TILEMAP_BLOCKED_NO_TBL", 0) or 0),
                "texts_abbreviated": int(layout_adjusted.get("adjusted_count", 0) or 0),
                "relocated_texts": int(len(relocated_texts)),
                "relocation_pool_bytes_used": int((pool_info or {}).get("bytes_used", 0) or 0),
                "auto_diff_ranges_count": int(translation_input.get("auto_generate_diff_ranges_count", 0) or 0),
                "id_override_rewritten": int(id_override_info.get("rewritten", 0) or 0),
                "guardrail_warning_count": int(len(guardrail_warnings)),
            },
            "diff_ranges": diff_ranges,
            "diff_outside_allowed": diff_outside,
            "crc32": crc_after.upper(),
            "rom_size": rom_size,
            "qa_final": qa_final,
            "qa_artifacts": qa_artifacts,
            "qa_gate": qa_gate_result,
            "runtime_coverage": runtime_coverage_result,
            "verified_100": bool(verified_100),
            "allowed_ranges_count": len(allowed_ranges),
            "checksums": {
                "before": {"crc32": crc_before, "sha256": sha_before},
                "after": {"crc32": crc_after, "sha256": sha_after},
            },
            "stats": stats,
            "application_metrics": application_metrics,
            "lines_count": len(translated),
        }
        proof_json = json.dumps(proof, indent=2, ensure_ascii=False)
        proof_path = out_dir / f"{crc_after.upper()}_proof.json"
        for tag in file_tags:
            (out_dir / f"{tag}_proof.json").write_text(proof_json, encoding="utf-8")

        # report.txt (resumo com evidências)
        top_reloc = sorted(relocated_items, key=lambda x: x.get("final_len", 0), reverse=True)[:10]
        report_lines = [
            f"CRC32={crc_after.upper()} ROM_SIZE={rom_size}",
            f"CHECKSUM_BEFORE_CRC32={crc_before}",
            f"CHECKSUM_BEFORE_SHA256={sha_before}",
            f"CHECKSUM_AFTER_CRC32={crc_after}",
            f"CHECKSUM_AFTER_SHA256={sha_after}",
            f"lines_count={len(translated)}",
            f"translation_input={translation_input.get('path')}",
            f"translation_file_sha256={translation_input.get('sha256', 'N/A')}",
            f"jsonl_declared_crc32={input_match_check.get('jsonl_declared_crc32')}",
            f"jsonl_declared_size={input_match_check.get('jsonl_declared_size')}",
            f"guardrail_warning_count={translation_input.get('guardrail_warning_count', 0)}",
            f"strict_ptbr_mode={str(bool(strict_ptbr_info.get('enabled', False))).lower()}",
            f"strict_ptbr_rewritten={strict_ptbr_info.get('rewritten', 0)}",
            f"strict_ptbr_overrides_loaded={strict_ptbr_info.get('overrides_loaded', 0)}",
            f"strict_ptbr_override_file={strict_ptbr_info.get('override_file')}",
            f"auto_pt_fragment_rewrites={translation_input.get('auto_pt_fragment_rewrites', 0)}",
            f"auto_non_pt_rewrites={translation_input.get('auto_non_pt_rewrites', 0)}",
            f"auto_english_cleanup_rewrites={translation_input.get('auto_english_cleanup_rewrites', 0)}",
            f"normalize_nfc={str(bool(translation_input.get('normalize_nfc', True))).lower()}",
            f"custom_dictionary_path={translation_input.get('custom_dictionary_path')}",
            f"custom_dictionary_entries={translation_input.get('custom_dictionary_entries', 0)}",
            f"custom_dictionary_rewrites={translation_input.get('custom_dictionary_rewrites', 0)}",
            f"translation_api_fallback={str(bool(translation_input.get('translation_api_fallback', False))).lower()}",
            f"translation_service={translation_input.get('translation_service')}",
            f"translation_api_calls={translation_input.get('translation_api_calls', 0)}",
            f"translation_api_success={translation_input.get('translation_api_success', 0)}",
            f"translation_api_rewrites={translation_input.get('translation_api_rewrites', 0)}",
            f"glyph_injection_enabled={str(bool(translation_input.get('glyph_injection_enabled', True))).lower()}",
            f"glyph_font={translation_input.get('glyph_font')}",
            f"glyph_allowed_ranges_count={translation_input.get('glyph_allowed_ranges_count', 0)}",
            f"auto_relocate_if_needed={str(bool(translation_input.get('auto_relocate_if_needed', True))).lower()}",
            f"relocation_requested_items={translation_input.get('relocation_requested_items', 0)}",
            f"relocation_applied_items={translation_input.get('relocation_applied_items', 0)}",
            f"relocation_forbidden_ranges_count={translation_input.get('relocation_forbidden_ranges_count', 0)}",
            f"auto_generate_diff_ranges={str(bool(translation_input.get('auto_generate_diff_ranges', True))).lower()}",
            f"auto_generate_diff_ranges_generated={str(bool(translation_input.get('auto_generate_diff_ranges_generated', False))).lower()}",
            f"auto_generate_diff_ranges_count={translation_input.get('auto_generate_diff_ranges_count', 0)}",
            f"auto_generate_diff_ranges_skipped_existing={translation_input.get('auto_generate_diff_ranges_skipped_existing', 0)}",
            f"auto_generate_diff_ranges_margin_start={translation_input.get('auto_generate_diff_ranges_margin_start', 0)}",
            f"auto_generate_diff_ranges_margin_end={translation_input.get('auto_generate_diff_ranges_margin_end', 0)}",
            f"auto_generate_diff_ranges_merge_gap={translation_input.get('auto_generate_diff_ranges_merge_gap', 0)}",
            f"tilemap_require_tbl={str(bool(translation_input.get('tilemap_require_tbl', True))).lower()}",
            f"require_tilemap={str(bool(translation_input.get('require_tilemap', True))).lower()}",
            f"tilemap_tbl_available={str(bool(translation_input.get('tilemap_tbl_available', True))).lower()}",
            f"tilemap_entries_detected={translation_input.get('tilemap_entries_detected', 0)}",
            f"external_allowed_ranges_count={translation_input.get('external_allowed_ranges_count', 0)}",
            f"external_allowed_ranges_source={translation_input.get('external_allowed_ranges_source')}",
            f"game_engineering_profile_id={game_engineering_info.get('profile_id')}",
            f"game_engineering_has_crc_profile={str(bool(game_engineering_info.get('has_crc_profile', False))).lower()}",
            f"game_engineering_rewritten={int(self._game_engineering_text_changes)}",
            f"game_engineering_compression={json.dumps(compression_policy if isinstance(compression_policy, dict) else {}, ensure_ascii=False)}",
            "",
            "INPUT_MATCH_CHECK:",
            f"  rom_crc32_match={str(bool(input_match_check.get('rom_crc32_match', False))).lower()}",
            f"  rom_size_match={str(bool(input_match_check.get('rom_size_match', False))).lower()}",
            f"  jsonl_declared_crc32={input_match_check.get('jsonl_declared_crc32')}",
            f"  jsonl_declared_size={input_match_check.get('jsonl_declared_size')}",
            "",
            "ORDERING_CHECK:",
            f"  is_sorted_by_offset={str(bool(ordering_check.get('is_sorted_by_offset', False))).lower()}",
            f"  seq_consistent={str(bool(ordering_check.get('seq_consistent', False))).lower()}",
            f"  first_10_offsets={json.dumps(ordering_check.get('first_10_offsets', []), ensure_ascii=False)}",
            f"  last_10_offsets={json.dumps(ordering_check.get('last_10_offsets', []), ensure_ascii=False)}",
            "",
            "COVERAGE_CHECK:",
            f"  min_offset={coverage_check.get('min_offset')}",
            f"  max_offset={coverage_check.get('max_offset')}",
            f"  items_total={coverage_check.get('items_total')}",
            f"  count_offsets_below_0x10000={coverage_check.get('count_offsets_below_0x10000')}",
            f"  first_20_items_summary={json.dumps(coverage_check.get('first_20_items_summary', []), ensure_ascii=False)}",
            "",
            "DISPLAYED_TRACE:",
            f"  trace_path={displayed_trace_primary}",
            f"  missing_path={missing_displayed_primary}",
            f"  coverage_summary_path={coverage_summary_primary}",
            f"  displayed_trace_items_total={coverage_summary.get('displayed_trace_items_total', 0)}",
            f"  displayed_trace_mapped_items={coverage_summary.get('displayed_trace_mapped_items', 0)}",
            f"  displayed_trace_unmapped_items={coverage_summary.get('displayed_trace_unmapped_items', 0)}",
            f"  displayed_trace_needs_review_items={coverage_summary.get('displayed_trace_needs_review_items', 0)}",
            f"  displayed_trace_not_applied_items={coverage_summary.get('displayed_trace_not_applied_items', 0)}",
            f"  displayed_trace_skip_displayed_count={coverage_summary.get('displayed_trace_skip_displayed_count', 0)}",
            f"  displayed_trace_english_residual_count={coverage_summary.get('displayed_trace_english_residual_count', 0)}",
            f"  displayed_trace_same_as_source_phrase_count={coverage_summary.get('displayed_trace_same_as_source_phrase_count', 0)}",
            f"  missing_displayed_text_count={coverage_summary.get('missing_displayed_text_count', 0)}",
            "",
            "RESUMO:",
            f"  OK={stats.get('OK', 0)}",
            f"  REPOINT={stats.get('REPOINT', 0)}",
            f"  REFORM={stats.get('REFORM', 0)}",
            f"  WRAP={stats.get('WRAP', 0)}",
            f"  TRUNC/SHORT={stats.get('TRUNC', 0)}",
            f"  BLOCKED={stats.get('BLOCKED', 0)}",
            f"  PTR_FROM_META={stats.get('PTR_FROM_META', 0)}",
            f"  STRICT_PTBR_REWRITTEN={stats.get('STRICT_PTBR', 0)}",
            f"  GAME_ENGINEERING_REWRITE={stats.get('GAME_ENGINEERING_REWRITE', 0)}",
            f"  AUTO_UNBLOCK_REVIEW={stats.get('AUTO_UNBLOCK_REVIEW', 0)}",
            f"  TILEMAP_BLOCKED_NO_TBL={stats.get('TILEMAP_BLOCKED_NO_TBL', 0)}",
            f"  LAYOUT_ADJUSTED={stats.get('LAYOUT_ADJUSTED', 0)}",
            f"  LAYOUT_SHORT_STYLE={stats.get('LAYOUT_SHORT_STYLE', 0)}",
            f"  APPLIED_KEYS={stats.get('APPLIED_KEYS', 0)}",
            f"  STRUCTURAL_SKIPPED={stats.get('STRUCTURAL_SKIPPED', 0)}",
            f"  BLOCKED_REAL={stats.get('BLOCKED_REAL', 0)}",
            f"  EFFECTIVE_TOTAL_KEYS={stats.get('EFFECTIVE_TOTAL_KEYS', 0)}",
            f"  UNRESOLVED_OVERLAP={stats.get('UNRESOLVED_OVERLAP', 0)}",
            f"  RESOLVED_OVERLAP={stats.get('RESOLVED_OVERLAP', 0)}",
            f"  COVERED_WITH_OVERLAP_KEYS={stats.get('COVERED_WITH_OVERLAP_KEYS', 0)}",
            f"  COVERED_WITH_OVERLAP_PERCENT={stats.get('COVERED_WITH_OVERLAP_PERCENT', 0.0)}",
            f"  CHARSET_FALLBACK_ASCII={charset_stats.get('ascii_fallback_chars', 0)}",
            f"  CHARSET_FALLBACK_TILEMAP={charset_stats.get('tilemap_fallback_chars', 0)}",
            f"  CHARSET_POLICY={charset_policy}",
            f"  GLYPH_INJECTION={'YES' if glyph_injection_report and glyph_injection_report.get('success') else 'NO'}",
            f"  GLYPH_INJECTED_COUNT={glyph_injection_report.get('injected_count', 0) if glyph_injection_report else 0}",
            f"  GLYPH_INJECTED_BASE={glyph_injection_report.get('injected_from_base_count', 0) if glyph_injection_report else 0}",
            f"  GLYPH_INJECTED_VERDANA={glyph_injection_report.get('injected_from_verdana_count', 0) if glyph_injection_report else 0}",
            f"  GLYPH_SOURCE_FONT={glyph_injection_report.get('source_font', '') if glyph_injection_report else ''}",
            f"  GLYPH_MISSING_BEFORE={len(glyph_injection_report.get('missing_before', [])) if glyph_injection_report else 0}",
            f"  GLYPH_MISSING_AFTER={len(glyph_injection_report.get('missing_after', [])) if glyph_injection_report else 0}",
            "",
            "UI_METRICS:",
            f"  UI_ITEMS_FOUND={stats.get('UI_ITEMS_FOUND', 0)}",
            f"  UI_ITEMS_EXTRACTED={stats.get('UI_ITEMS_EXTRACTED', 0)}",
            f"  UI_ITEMS_TRANSLATED={stats.get('UI_ITEMS_TRANSLATED', 0)}",
            f"  UI_ITEMS_REINSERTED={stats.get('UI_ITEMS_REINSERTED', 0)}",
            f"  UI_ITEMS_BLOCKED={stats.get('UI_ITEMS_BLOCKED', 0)}",
            "",
            "COMPRESSED_BLOCK_REINSERTION:",
            f"  enabled={str(bool(compressed_block_reinsertion.get('enabled', False))).lower()}",
            f"  candidates={compressed_block_reinsertion.get('candidates', 0)}",
            f"  blocks_total={compressed_block_reinsertion.get('blocks_total', 0)}",
            f"  blocks_applied={compressed_block_reinsertion.get('blocks_applied', 0)}",
            f"  blocks_relocated={compressed_block_reinsertion.get('blocks_relocated', 0)}",
            f"  pointer_updates={compressed_block_reinsertion.get('pointer_updates', 0)}",
            f"  inserted_items={compressed_block_reinsertion.get('inserted_items', 0)}",
            f"  truncated_items={compressed_block_reinsertion.get('truncated_items', 0)}",
            f"  blocked_items={compressed_block_reinsertion.get('blocked_items', 0)}",
            f"  roundtrip_fail_blocks={compressed_block_reinsertion.get('roundtrip_fail_blocks', 0)}",
            f"  unsupported_algorithm_blocks={compressed_block_reinsertion.get('unsupported_algorithm_blocks', 0)}",
            "",
            "COBERTURA:",
            f"  missing_in_translated={coverage.get('missing_in_translated', 0)}",
            f"  empty_translated={coverage.get('empty_translated', 0)}",
            f"  same_as_source_raw={coverage.get('same_as_source_raw', 0)}",
            f"  untranslated_same_as_source={coverage.get('untranslated_same_as_source', 0)}",
            f"  same_as_source_non_actionable={coverage.get('same_as_source_non_actionable', 0)}",
            f"  translated_ok={coverage.get('translated_ok', 0)}",
            "",
            "QUALIDADE_IDIOMA:",
            f"  ptbr_rate={translation_quality.get('ptbr_rate', 0)}%",
            f"  ptbr_likely={translation_quality.get('ptbr_likely', 0)}",
            f"  english_likely={translation_quality.get('english_likely', 0)}",
            f"  non_ptbr_suspect={translation_quality.get('non_ptbr_suspect', 0)}",
            "",
            "QA_FINAL:",
            f"  overall_pass={str(bool((qa_final or {}).get('overall_pass', False))).lower()}",
            f"  quality_score_percent={(qa_final or {}).get('quality_score_percent')}",
            "  required_failed="
            + json.dumps((qa_final or {}).get("required_failed", []), ensure_ascii=False),
            "  required_unknown="
            + json.dumps((qa_final or {}).get("required_unknown", []), ensure_ascii=False),
            f"  qa_json={(qa_artifacts or {}).get('json')}",
            f"  qa_txt={(qa_artifacts or {}).get('txt')}",
            "",
            "QA_GATE:",
            f"  pass={str(bool((qa_gate_result or {}).get('pass', False))).lower()}",
            "  failed_checks="
            + json.dumps((qa_gate_result or {}).get("failed_checks", []), ensure_ascii=False),
            f"  pure_count={(qa_gate_result or {}).get('metrics', {}).get('pure_count', 0)}",
            f"  translated_count={(qa_gate_result or {}).get('metrics', {}).get('translated_count', 0)}",
            f"  missing_count={(qa_gate_result or {}).get('metrics', {}).get('missing_count', 0)}",
            f"  extra_count={(qa_gate_result or {}).get('metrics', {}).get('extra_count', 0)}",
            f"  offset_none_count={(qa_gate_result or {}).get('metrics', {}).get('offset_none_count', 0)}",
            f"  pointer_invalid_count={(qa_gate_result or {}).get('metrics', {}).get('pointer_invalid_count', 0)}",
            f"  terminator_missing_count={(qa_gate_result or {}).get('metrics', {}).get('terminator_missing_count', 0)}",
            "",
            "RUNTIME_COVERAGE:",
            f"  provided={str(bool((runtime_coverage_result or {}).get('provided', False))).lower()}",
            f"  pass={str(bool((runtime_coverage_result or {}).get('pass', False))).lower()}",
            f"  reason={(runtime_coverage_result or {}).get('reason', '')}",
            f"  runtime_unmapped_total={(runtime_coverage_result or {}).get('runtime_unmapped_total', 0)}",
            f"  runtime_untranslated_total={(runtime_coverage_result or {}).get('runtime_untranslated_total', 0)}",
            f"  runtime_unresolved_total={(runtime_coverage_result or {}).get('runtime_unresolved_total', 0)}",
            f"  runtime_evidence_assessable_total={(runtime_coverage_result or {}).get('runtime_evidence_assessable_total', 0)}",
            f"  coverage_hits_percent={(runtime_coverage_result or {}).get('coverage_hits_percent', 0.0)}",
            "",
            "APPLICATION_METRICS:",
            f"  keys_total={application_metrics.get('keys_total', 0)}",
            f"  effective_total_keys={application_metrics.get('effective_total_keys', 0)}",
            f"  applied_keys={application_metrics.get('applied_keys', 0)}",
            f"  structural_skipped_keys={application_metrics.get('structural_skipped_keys', 0)}",
            f"  blocked_real_keys={application_metrics.get('blocked_real_keys', 0)}",
            f"  unresolved_overlap_keys={application_metrics.get('unresolved_overlap_keys', 0)}",
            f"  applied_percent_global={application_metrics.get('applied_percent_global', 0.0)}",
            f"  applied_percent_effective={application_metrics.get('applied_percent_effective', 0.0)}",
            f"  blocked_percent_global={application_metrics.get('blocked_percent_global', 0.0)}",
            f"  blocked_percent_effective={application_metrics.get('blocked_percent_effective', 0.0)}",
            "",
            "VERIFICATION:",
            f"  verified_100={str(bool(verified_100)).lower()}",
            "",
            "EVIDENCIAS:",
            f"  AUDIT_ITEMS={evidence.get('AUDIT_ITEMS', 0)}",
            f"  AUDIT_UNKNOWN_BYTES_TOTAL={evidence.get('AUDIT_UNKNOWN_BYTES_TOTAL', 0)}",
            f"  AUDIT_ROUNDTRIP_FAIL_COUNT={evidence.get('AUDIT_ROUNDTRIP_FAIL_COUNT', 0)}",
            f"  AUDIT_OVERLAP_ITEMS={evidence.get('AUDIT_OVERLAP_ITEMS', 0)}",
            f"  REINSERTION_SAFE_COUNT={evidence.get('REINSERTION_SAFE_COUNT', 0)}",
            f"  UI_ITEMS_FOUND={evidence.get('UI_ITEMS_FOUND', 0)}",
            f"  UI_ITEMS_EXTRACTED={evidence.get('UI_ITEMS_EXTRACTED', 0)}",
            f"  UI_ITEMS_TRANSLATED={evidence.get('UI_ITEMS_TRANSLATED', 0)}",
            f"  UI_ITEMS_REINSERTED={evidence.get('UI_ITEMS_REINSERTED', 0)}",
            f"  UI_ITEMS_BLOCKED={evidence.get('UI_ITEMS_BLOCKED', 0)}",
            f"  ITEMS_TOTAL={evidence.get('AUDIT_ITEMS', 0)}",
            f"  displayed_trace_skip_displayed_count={evidence.get('displayed_trace_skip_displayed_count', 0)}",
            f"  displayed_trace_english_residual_count={evidence.get('displayed_trace_english_residual_count', 0)}",
            f"  displayed_trace_same_as_source_phrase_count={evidence.get('displayed_trace_same_as_source_phrase_count', 0)}",
            f"  not_translated_count={evidence.get('not_translated_count', 0)}",
            f"  same_as_source_phrase_count={evidence.get('same_as_source_phrase_count', 0)}",
            f"  same_as_source_raw_count={evidence.get('same_as_source_raw_count', 0)}",
            f"  same_as_source_non_actionable_count={evidence.get('same_as_source_non_actionable_count', 0)}",
            f"  truncated_count={evidence.get('truncated_count', 0)}",
            f"  non_ptbr_suspect_count={evidence.get('non_ptbr_suspect_count', 0)}",
            f"  english_likely_count={evidence.get('english_likely_count', 0)}",
            f"  unchanged_equal_src_count={evidence.get('unchanged_equal_src_count', 0)}",
            f"  suspicious_non_pt_count={evidence.get('suspicious_non_pt_count', 0)}",
            f"  rom_vs_translated_mismatch_count={evidence.get('rom_vs_translated_mismatch_count', 0)}",
            f"  placeholder_fail_count={evidence.get('placeholder_fail_count', 0)}",
            f"  terminator_missing_count={evidence.get('terminator_missing_count', 0)}",
            "",
            "PROBLEM_INDEX:",
            f"  unchanged_equal_src={issue_index_after.get('counts', {}).get('unchanged_equal_src', 0)}",
            f"  suspicious_non_pt={issue_index_after.get('counts', {}).get('suspicious_non_pt', 0)}",
            f"  rom_vs_translated_mismatch={issue_index_after.get('counts', {}).get('rom_vs_translated_mismatch', 0)}",
            f"  placeholder_fail={issue_index_after.get('counts', {}).get('placeholder_fail', 0)}",
            f"  terminator_missing={issue_index_after.get('counts', {}).get('terminator_missing', 0)}",
            "",
        ]
        if limitations:
            report_lines.append("LIMITACOES:")
            for item in limitations:
                report_lines.append(f"  - {item}")
            report_lines.append("")
        if delta_incremental:
            before_counts = (delta_incremental.get("before", {}) or {}).get("counts", {}) or {}
            reported_before_counts = (delta_incremental.get("reported_before", {}) or {}).get("counts", {}) or {}
            after_counts = (delta_incremental.get("after", {}) or {}).get("counts", {}) or {}
            criteria = delta_incremental.get("criteria", {}) or {}
            report_lines.append("DELTA_INCREMENTAL:")
            report_lines.append(f"  enabled={str(bool(delta_incremental.get('enabled', False))).lower()}")
            report_lines.append(f"  delta_path={delta_incremental.get('delta_path')}")
            report_lines.append(f"  source_path={delta_incremental.get('source_path')}")
            report_lines.append(f"  problem_keys_total={delta_incremental.get('problem_keys_total', 0)}")
            report_lines.append("  before_counts=" + json.dumps(before_counts, ensure_ascii=False))
            report_lines.append("  reported_before_counts=" + json.dumps(reported_before_counts, ensure_ascii=False))
            report_lines.append("  after_counts=" + json.dumps(after_counts, ensure_ascii=False))
            report_lines.append(
                "  criteria="
                + json.dumps(
                    {k: bool(v) for k, v in criteria.items()},
                    ensure_ascii=False,
                )
            )
            report_lines.append("")
        if game_engineering_info:
            report_lines.append("GAME_ENGINEERING:")
            report_lines.append(f"  enabled={str(bool(game_engineering_info.get('enabled', False))).lower()}")
            report_lines.append(
                f"  has_crc_profile={str(bool(game_engineering_info.get('has_crc_profile', False))).lower()}"
            )
            report_lines.append(f"  profile_id={game_engineering_info.get('profile_id')}")
            report_lines.append(f"  profile_name={game_engineering_info.get('profile_name')}")
            report_lines.append(f"  profile_version={game_engineering_info.get('profile_version')}")
            report_lines.append(f"  profile_file={game_engineering_info.get('profile_file')}")
            report_lines.append(f"  text_rewrites={int(self._game_engineering_text_changes)}")
            report_lines.append(
                "  compression_policy="
                + json.dumps(
                    compression_policy if isinstance(compression_policy, dict) else {},
                    ensure_ascii=False,
                )
            )
            report_lines.append("")
        if guardrail_warnings:
            report_lines.append("GUARDRAIL_WARNINGS:")
            for warn in guardrail_warnings:
                report_lines.append(f"  - {warn}")
            report_lines.append("")
        strict_changes = strict_ptbr_info.get("changes") or []
        if strict_changes:
            report_lines.append("STRICT_PTBR_CHANGES:")
            for change in strict_changes:
                report_lines.append(
                    f"  - key={change.get('key')} reason={change.get('reason')} "
                    f"before={change.get('before')} => after={change.get('after')}"
                )
            report_lines.append("")
        id_override_changes = id_override_info.get("changes") or []
        if id_override_info.get("override_file") or id_override_changes:
            report_lines.append("ID_OVERRIDE:")
            report_lines.append(f"  enabled={str(bool(id_override_info.get('enabled', False))).lower()}")
            report_lines.append(f"  override_file={id_override_info.get('override_file')}")
            report_lines.append(
                f"  overrides_loaded={int(id_override_info.get('overrides_loaded', 0) or 0)}"
            )
            report_lines.append(f"  matched={int(id_override_info.get('matched', 0) or 0)}")
            report_lines.append(f"  rewritten={int(id_override_info.get('rewritten', 0) or 0)}")
            if id_override_changes:
                report_lines.append("  changes:")
                for change in id_override_changes[:20]:
                    report_lines.append(
                        f"    - key={change.get('key')} before={change.get('before')} => after={change.get('after')}"
                    )
            warn_list = id_override_info.get("warnings") or []
            if warn_list:
                report_lines.append("  warnings:")
                for warn in warn_list[:20]:
                    report_lines.append(f"    - {warn}")
            report_lines.append("")
        if layout_adjusted.get("adjusted_count", 0):
            report_lines.append("LAYOUT_ADJUSTED:")
            report_lines.append(f"  adjusted_count={layout_adjusted.get('adjusted_count', 0)}")
            report_lines.append(f"  short_style_count={layout_adjusted.get('short_style_count', 0)}")
            for sample in layout_adjusted.get("examples", [])[:20]:
                report_lines.append(
                    f"  - key={sample.get('key')} action={sample.get('action')} strategy={sample.get('strategy')}"
                )
            report_lines.append("")
        report_lines.append("CONSOLIDATED_PIPELINE:")
        report_lines.append(
            f"  glyphs_injected={int((glyph_injection_report or {}).get('injected_count', 0) or 0)}"
        )
        report_lines.append(
            f"  glyphs_base={int((glyph_injection_report or {}).get('injected_from_base_count', 0) or 0)}"
        )
        report_lines.append(
            f"  glyphs_verdana={int((glyph_injection_report or {}).get('injected_from_verdana_count', 0) or 0)}"
        )
        report_lines.append(
            f"  tilemaps_ignored_no_tbl={int(stats.get('TILEMAP_BLOCKED_NO_TBL', 0) or 0)}"
        )
        report_lines.append(
            f"  textos_abreviados={int(layout_adjusted.get('adjusted_count', 0) or 0)}"
        )
        report_lines.append(
            f"  realocados={int(len(relocated_texts))}"
        )
        report_lines.append(
            f"  pool_bytes_used={int((pool_info or {}).get('bytes_used', 0) or 0)}"
        )
        report_lines.append(
            f"  auto_diff_ranges={int((translation_input.get('auto_generate_diff_ranges_count', 0) or 0))}"
        )
        report_lines.append(
            f"  id_override_rewritten={int(id_override_info.get('rewritten', 0) or 0)}"
        )
        report_lines.append(
            f"  avisos={int(len(guardrail_warnings))}"
        )
        report_lines.append("")
        if pool_info:
            report_lines.append("POOL:")
            report_lines.append(f"  start={pool_info.get('start_hex')}")
            report_lines.append(f"  end={pool_info.get('end_hex')}")
            report_lines.append(f"  bytes_used={pool_info.get('bytes_used')}")
            report_lines.append(f"  bytes_free={pool_info.get('bytes_free')}")
            report_lines.append(f"  alignment={pool_info.get('alignment')}")
            report_lines.append(f"  filler_byte={pool_info.get('filler_byte')}")
            report_lines.append(f"  expanded={pool_info.get('expanded')}")
            report_lines.append("")

        if diff_blocked:
            report_lines.append("DIFF_RANGES: BLOQUEADO (alterações fora das regiões permitidas)")
        report_lines.append("")
        report_lines.append("TOP REALOCADOS (maiores):")
        if top_reloc:
            for item in top_reloc:
                report_lines.append(
                    f"  - {item.get('key')} old=0x{item.get('old_offset',0):X} new=0x{item.get('new_offset',0):X} len={item.get('final_len')}"
                )
        else:
            report_lines.append("  (nenhum)")
        if relocated_texts:
            report_lines.append("")
            report_lines.append("RELOCATED_TEXTS:")
            for row in relocated_texts[:20]:
                report_lines.append(
                    "  - "
                    f"id={row.get('id')} old=0x{int(row.get('old_offset', 0) or 0):X} "
                    f"new=0x{int(row.get('new_offset', 0) or 0):X} "
                    f"old_len={row.get('old_len')} new_len={row.get('new_len')} "
                    f"ptrs={len(row.get('pointer_updates', []) or [])}"
                )

        cmp_applied_samples = (compressed_block_reinsertion.get("examples", {}) or {}).get("applied", []) or []
        if cmp_applied_samples:
            report_lines.append("")
            report_lines.append("EXEMPLOS_COMPRESSED_APPLIED:")
            for sample in cmp_applied_samples[:8]:
                report_lines.append(
                    f"  - {sample.get('key')} action={sample.get('action')} "
                    f"off={sample.get('compressed_offset')} alg={sample.get('compression_algorithm')} "
                    f"relocated={sample.get('relocated')}"
                )

        cmp_blocked_samples = (compressed_block_reinsertion.get("examples", {}) or {}).get("blocked", []) or []
        if cmp_blocked_samples:
            report_lines.append("")
            report_lines.append("EXEMPLOS_COMPRESSED_BLOCKED:")
            for sample in cmp_blocked_samples[:8]:
                report_lines.append(
                    f"  - {sample.get('key')} reason={sample.get('reason')}"
                )

        non_pt_samples = translation_quality.get("examples", {}).get("non_ptbr_suspect", [])
        if non_pt_samples:
            report_lines.append("")
            report_lines.append("EXEMPLOS_NON_PTBR:")
            for sample in non_pt_samples[:8]:
                report_lines.append(f"  - {sample.get('key')}: {sample.get('text')}")

        unchanged_samples = issue_index_after.get("examples", {}).get("unchanged_equal_src", [])
        if unchanged_samples:
            report_lines.append("")
            report_lines.append("EXEMPLOS_UNCHANGED_EQUAL_SRC:")
            for sample in unchanged_samples[:8]:
                report_lines.append(
                    f"  - {sample.get('key')}: src={sample.get('src')} | dst={sample.get('dst')}"
                )

        mismatch_samples = issue_index_after.get("examples", {}).get("rom_vs_translated_mismatch", [])
        if mismatch_samples:
            report_lines.append("")
            report_lines.append("EXEMPLOS_ROM_VS_TRANSLATED_MISMATCH:")
            for sample in mismatch_samples[:8]:
                report_lines.append(
                    f"  - {sample.get('key')}: off={sample.get('offset')} rom={sample.get('rom_text')} | dst={sample.get('dst')}"
                )

        placeholder_samples = issue_index_after.get("examples", {}).get("placeholder_fail", [])
        if placeholder_samples:
            report_lines.append("")
            report_lines.append("EXEMPLOS_PLACEHOLDER_FAIL:")
            for sample in placeholder_samples[:8]:
                report_lines.append(
                    f"  - {sample.get('key')}: missing={sample.get('missing_tokens')} src={sample.get('src')} | dst={sample.get('dst')}"
                )

        term_samples = issue_index_after.get("examples", {}).get("terminator_missing", [])
        if term_samples:
            report_lines.append("")
            report_lines.append("EXEMPLOS_TERMINATOR_MISSING:")
            for sample in term_samples[:8]:
                report_lines.append(
                    f"  - {sample.get('key')}: off={sample.get('offset')} expected={sample.get('expected_terminator')}"
                )

        if ui_blocked_details:
            report_lines.append("")
            report_lines.append("UI_BLOCKED_DETAILS:")
            for sample in ui_blocked_details[:50]:
                report_lines.append(
                    f"  - key={sample.get('key')} off={sample.get('offset')} reason={sample.get('reason')}"
                )

        same_non_actionable = evidence.get("examples", {}).get("same_as_source_non_actionable", [])
        if same_non_actionable:
            report_lines.append("")
            report_lines.append("EXEMPLOS_SAME_AS_SOURCE_NON_ACTIONABLE:")
            for sample in same_non_actionable[:8]:
                report_lines.append(
                    f"  - {sample.get('key')}: src={sample.get('src')} | dst={sample.get('dst')}"
                )

        trunc_samples = evidence.get("examples", {}).get("truncated", [])
        if trunc_samples:
            report_lines.append("")
            report_lines.append("EXEMPLOS_TRUNCADOS:")
            for sample in trunc_samples[:8]:
                report_lines.append(
                    f"  - {sample.get('key')} action={sample.get('action')} max_len={sample.get('max_len')} new_len={sample.get('new_len')}"
                )

        if delta_incremental:
            before_examples = (delta_incremental.get("before", {}) or {}).get("examples", {}) or {}
            report_lines.append("")
            report_lines.append("DELTA_BEFORE_EXAMPLES:")
            for cat in self.DELTA_ISSUE_CATEGORIES:
                samples = before_examples.get(cat, [])
                if not samples:
                    continue
                report_lines.append(f"  {cat}:")
                for sample in samples[:3]:
                    report_lines.append(f"    - {json.dumps(sample, ensure_ascii=False)}")

        report_txt = "\n".join(report_lines)
        report_txt_path = out_dir / f"{crc_after.upper()}_report.txt"
        for tag in file_tags:
            (out_dir / f"{tag}_report.txt").write_text(report_txt, encoding="utf-8")

        # Relatório de reinserção
        if report_path is None:
            report_path = out_dir / f"{crc_after.upper()}_reinsertion_report.json"

        report = {
            "crc32": crc_after.upper(),
            "rom_size": rom_size,
            "dry_run": dry_run,
            "strict": strict,
            "checksums": {
                "before": {"crc32": crc_before, "sha256": sha_before},
                "after": {"crc32": crc_after, "sha256": sha_after},
            },
            "stats": stats,
            "translation_input": translation_input,
            "input_match_check": input_match_check,
            "ordering_check": ordering_check,
            "coverage_check": coverage_check,
            "strict_ptbr": strict_ptbr_info,
            "id_override": id_override_info,
            "game_engineering": {
                "profile": game_engineering_info,
                "text_rewrites": int(self._game_engineering_text_changes),
            },
            "guardrail_warnings": list(guardrail_warnings),
            "translation_quality": translation_quality,
            "layout_adjusted": layout_adjusted,
            "glyph_injection": glyph_injection_report,
            "coverage": coverage,
            "application_metrics": application_metrics,
            "relocated_texts": relocated_texts,
            "relocated_items": relocated_items,
            "relocation_pool": pool_info if pool_info else None,
            "consolidated": {
                "glyphs_injected": int((glyph_injection_report or {}).get("injected_count", 0) or 0),
                "glyphs_base": int((glyph_injection_report or {}).get("injected_from_base_count", 0) or 0),
                "glyphs_verdana": int((glyph_injection_report or {}).get("injected_from_verdana_count", 0) or 0),
                "tilemaps_ignored_no_tbl": int(stats.get("TILEMAP_BLOCKED_NO_TBL", 0) or 0),
                "texts_abbreviated": int(layout_adjusted.get("adjusted_count", 0) or 0),
                "relocated_texts": int(len(relocated_texts)),
                "relocation_pool_bytes_used": int((pool_info or {}).get("bytes_used", 0) or 0),
                "auto_diff_ranges_count": int(translation_input.get("auto_generate_diff_ranges_count", 0) or 0),
                "id_override_rewritten": int(id_override_info.get("rewritten", 0) or 0),
                "guardrail_warning_count": int(len(guardrail_warnings)),
            },
            "ui_metrics": {
                "UI_ITEMS_FOUND": int(ui_found_count),
                "UI_ITEMS_EXTRACTED": int(ui_extracted_count),
                "UI_ITEMS_TRANSLATED": int(ui_translated_count),
                "UI_ITEMS_REINSERTED": int(ui_reinserted_count),
                "UI_ITEMS_BLOCKED": int(ui_blocked_count),
                "blocked_items": list(ui_blocked_details),
            },
            "displayed_text_trace": {
                "items_total": int(len(displayed_trace_rows)),
                "path": displayed_trace_primary,
                "paths_by_tag": displayed_trace_paths,
            },
            "missing_displayed_text": {
                "items_total": int(len(missing_displayed_rows)),
                "path": missing_displayed_primary,
                "paths_by_tag": missing_displayed_paths,
            },
            "coverage_summary": coverage_summary,
            "coverage_summary_path": coverage_summary_primary,
            "coverage_summary_paths_by_tag": coverage_summary_paths,
            "issue_index": issue_index_after,
            "delta_incremental": delta_incremental,
            "compressed_block_reinsertion": compressed_block_reinsertion,
            "qa_final": qa_final,
            "qa_artifacts": qa_artifacts,
            "qa_gate": qa_gate_result,
            "runtime_coverage": runtime_coverage_result,
            "verified_100": bool(verified_100),
            "evidence": evidence,
            "items": items_report,
            "diff_ranges": diff_ranges,
            "diff_outside_allowed": diff_outside,
            "allowed_ranges_count": len(allowed_ranges),
            "lines_count": len(translated),
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        ensure_parent_dir(report_path)
        report_json = json.dumps(report, indent=2, ensure_ascii=False)
        report_path.write_text(report_json, encoding="utf-8")
        for tag in file_tags:
            alias_path = out_dir / f"{tag}_reinsertion_report.json"
            alias_path.write_text(report_json, encoding="utf-8")

        if diff_blocked and not dry_run:
            raise ReinsertionError(
                "Patch bloqueado: alterações fora das regiões permitidas (ver diff_ranges)."
            )

        return output_rom_path, stats


# compat import antigo
SMSReinserter = SegaMasterSystemReinserter


class SegaReinserter:
    """Wrapper com API compatível com GUI (interface_tradutor_final.py)."""

    def __init__(self, rom_path: str):
        self.rom_path = Path(rom_path)
        self._core = SegaMasterSystemReinserter()
        self._core.set_target_rom(self.rom_path)
        self.stats = {
            "inserted": 0,
            "truncated": 0,
            "skipped": 0,
            "forced": 0,
            "structural_skipped": 0,
            "effective_total": 0,
        }
        self._translations: Dict[str, str] = {}
        self._translated_path: Optional[Path] = None
        self._jsonl_meta: Dict[str, Dict[str, Any]] = {}
        self._meta_source_path: Optional[str] = None
        self._jsonl_declared_crc32: Optional[str] = None
        self._jsonl_declared_size: Optional[int] = None

    def _resolve_postpatch_profile_path(self) -> Optional[Path]:
        """
        Resolve arquivo de perfil pós-reinserção por plataforma.
        Mantém compatibilidade com SMS e habilita base SNES.
        """
        platform = str(getattr(self._core, "_target_platform", "SMS") or "SMS").upper()
        base_dir = Path(__file__).resolve().parent / "profiles"
        if platform == "SNES":
            return base_dir / "snes" / "post_reinsertion_crc_profiles.json"
        if platform == "SMS":
            return base_dir / "sms" / "post_reinsertion_crc_profiles.json"
        return None

    def get_runtime_policy(self) -> Dict[str, Any]:
        """Retorna snapshot da política ativa de reinserção/tradução."""
        policy = getattr(self._core, "_translation_runtime_policy", {})
        return dict(policy) if isinstance(policy, dict) else {}

    def get_guardrail_warnings(self) -> List[str]:
        """Lista avisos de guardrails desabilitados para log da interface."""
        collector = getattr(self._core, "_collect_guardrail_warnings", None)
        if callable(collector):
            try:
                return list(collector() or [])
            except Exception:
                return []
        return []

    def load_translations(self, translated_path: str) -> Dict[str, str]:
        """Carrega traduções de arquivo (TXT ou JSONL)."""
        path = Path(translated_path)
        if path.suffix.lower() == ".txt":
            # Preferência automática por JSONL PT-BR corrigido (quando existir).
            fixed_candidates = sorted(path.parent.glob("*fixed_ptbr*.jsonl"))
            if not fixed_candidates:
                fixed_candidates = sorted(path.parent.glob("*fixed*.jsonl"))
            if fixed_candidates:
                path = fixed_candidates[0]
        self._translated_path = path
        if path.suffix.lower() == ".jsonl":
            return self._load_jsonl(path)
        out = self._core.load_translated_blocks(path)
        if out:
            companion_meta, meta_path = self._load_companion_jsonl_meta(
                path, restrict_keys=set(out.keys())
            )
            if companion_meta:
                self._jsonl_meta.update(companion_meta)
                if meta_path:
                    self._meta_source_path = str(meta_path)
        return out

    def _key_from_obj(self, obj: Dict[str, Any]) -> str:
        """Gera chave estável para mapear JSONL <-> mapping."""
        if obj.get("id") is not None:
            return str(obj.get("id"))
        if obj.get("key"):
            return str(obj.get("key"))
        off = self._core._parse_int_value(obj.get("offset", 0), default=0)
        return f"0x{int(off):X}"

    def _is_empty_meta_value(self, value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return not value.strip()
        if isinstance(value, (list, dict, tuple, set)):
            return len(value) == 0
        return False

    def _merge_meta_preserving_binary_fields(
        self,
        base_meta: Optional[Dict[str, Any]],
        override_meta: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Merge seguro de metadados JSONL.
        Preserva campos críticos de controle/terminador quando vierem vazios no override.
        """
        base = dict(base_meta) if isinstance(base_meta, dict) else {}
        override = dict(override_meta) if isinstance(override_meta, dict) else {}
        merged = dict(base)
        merged.update(override)

        critical_fields = (
            "raw_bytes_hex",
            "ui_template_hex",
            "ui_printable_positions",
            "terminator",
            "terminator_hex",
            "raw_len",
            "encoding",
            "pointer_refs",
            "pointer_offsets",
            "max_len",
            "max_len_bytes",
            "offset",
            "rom_offset",
            "seq",
            "id",
        )
        for field in critical_fields:
            if self._is_empty_meta_value(merged.get(field)) and not self._is_empty_meta_value(base.get(field)):
                merged[field] = base.get(field)

        # Normaliza tipos comuns para evitar perda silenciosa de terminador/offset.
        term_val = self._core._parse_optional_int_value(merged.get("terminator"))
        if term_val is not None:
            merged["terminator"] = int(term_val) & 0xFF
        raw_len_val = self._core._parse_optional_int_value(merged.get("raw_len"))
        if raw_len_val is not None and int(raw_len_val) > 0:
            merged["raw_len"] = int(raw_len_val)
        return merged

    def _candidate_pure_jsonl_paths(self, path: Path) -> List[Path]:
        """Lista candidatos de pure_text.jsonl próximos ao arquivo traduzido."""
        candidates: List[Path] = []
        if path.suffix.lower() == ".jsonl":
            if path.name.endswith("_translated.jsonl"):
                candidates.append(
                    path.with_name(path.name.replace("_translated.jsonl", "_pure_text.jsonl"))
                )
            candidates.append(path.with_name(path.name.replace(".jsonl", "_pure_text.jsonl")))
        candidates.extend(sorted(path.parent.glob("*_pure_text.jsonl")))
        extracao_dir = path.parent.parent / "1_extracao"
        if extracao_dir.exists():
            candidates.extend(sorted(extracao_dir.glob("*_pure_text.jsonl")))
        candidates.append(path.parent / f"{path.parent.name}_pure_text.jsonl")

        seen: set = set()
        uniq: List[Path] = []
        for cand in candidates:
            try:
                rc = cand.resolve()
            except Exception:
                rc = cand
            if rc in seen:
                continue
            seen.add(rc)
            uniq.append(cand)
        return uniq

    def _load_companion_jsonl_meta(
        self,
        translated_path: Path,
        restrict_keys: Optional[set] = None,
    ) -> Tuple[Dict[str, Dict[str, Any]], Optional[Path]]:
        """Carrega metadados do pure_text.jsonl para ponteiros/texto original."""
        for cand in self._candidate_pure_jsonl_paths(translated_path):
            if not cand.exists():
                continue
            meta: Dict[str, Dict[str, Any]] = {}
            for line in cand.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(obj, dict):
                    continue
                if self._core._is_jsonl_meta_record(obj):
                    continue
                key = self._key_from_obj(obj)
                if restrict_keys is not None and key not in restrict_keys:
                    continue
                meta[key] = obj
            if meta:
                return meta, cand
        return {}, None

    def _load_jsonl(self, path: Path) -> Dict[str, str]:
        """Lê JSONL traduzido e retorna {key: texto}.

        Aceita campos do pipeline V1:
        - Texto: text_dst > translation > translated_text > translated > text
        - Chave: id (preferido) > key > offset formatado
        NÃO filtra por reinsertion_safe (decisão fica em reinsert())
        """
        out: Dict[str, str] = {}
        self._jsonl_meta = {}
        self._jsonl_declared_crc32 = None
        self._jsonl_declared_size = None
        parsed_rows: List[Dict[str, Any]] = []

        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if not isinstance(obj, dict):
                    continue
                if self._core._is_jsonl_meta_record(obj):
                    if obj.get("rom_crc32") is not None:
                        self._jsonl_declared_crc32 = str(obj.get("rom_crc32")).upper().strip()
                    if obj.get("rom_size") is not None:
                        self._jsonl_declared_size = self._core._parse_optional_int_value(obj.get("rom_size"))
                    continue

                if self._jsonl_declared_crc32 is None and obj.get("rom_crc32") is not None:
                    self._jsonl_declared_crc32 = str(obj.get("rom_crc32")).upper().strip()
                if self._jsonl_declared_size is None and obj.get("rom_size") is not None:
                    self._jsonl_declared_size = self._core._parse_optional_int_value(obj.get("rom_size"))

                # 1) Determina texto traduzido (ordem de prioridade pipeline V1)
                text = (obj.get("text_dst") or obj.get("translation") or
                        obj.get("translated_text") or obj.get("translated") or
                        obj.get("text"))
                if not isinstance(text, str) or not text.strip():
                    continue
                text = self._core._normalize_unicode_nfc(text)

                # 2) Normaliza offset para int (pode vir como string "0x000524")
                off = self._core._parse_optional_int_value(
                    obj.get("rom_offset", obj.get("offset"))
                )
                if off is None:
                    off = 0

                # 3) Determina chave: id (preferido pelo mapping) > key > offset
                if obj.get("id") is not None:
                    key = str(obj["id"])
                else:
                    key = obj.get("key") or f"0x{off:X}"
                seq_val = self._core._parse_optional_int_value(obj.get("seq"))
                parsed_rows.append(
                    {
                        "key": key,
                        "text": text,
                        "obj": obj,
                        "offset": int(off),
                        "seq": seq_val,
                    }
                )

            except json.JSONDecodeError:
                continue

        parsed_rows.sort(
            key=lambda row: (
                0 if row.get("seq") is not None else 1,
                row.get("seq") if row.get("seq") is not None else row.get("offset", 0),
                row.get("offset", 0),
                row.get("key", ""),
            )
        )

        for idx, row in enumerate(parsed_rows):
            key = str(row["key"])
            text = row["text"]
            obj = row["obj"]
            off = int(row.get("offset", 0))
            seq_val = row.get("seq")
            if seq_val is None:
                seq_val = idx
            obj["seq"] = int(seq_val)
            off_hex = f"0x{off:06X}"
            obj["offset"] = off_hex
            obj["rom_offset"] = off_hex
            if self._jsonl_declared_crc32:
                obj["rom_crc32"] = self._jsonl_declared_crc32
            if self._jsonl_declared_size is not None:
                obj["rom_size"] = int(self._jsonl_declared_size)

            # Preserva espaços no início/fim (alinhamento em tilemap)
            out[key] = text
            self._jsonl_meta[key] = self._merge_meta_preserving_binary_fields({}, obj)

        companion_meta, meta_path = self._load_companion_jsonl_meta(path, restrict_keys=set(out.keys()))
        if companion_meta:
            for key, meta in companion_meta.items():
                if key in self._jsonl_meta:
                    self._jsonl_meta[key] = self._merge_meta_preserving_binary_fields(
                        meta,
                        self._jsonl_meta[key],
                    )
                else:
                    self._jsonl_meta[key] = meta
            if meta_path:
                self._meta_source_path = str(meta_path)
        return out

    def _load_json_safe(self, path: Optional[Path]) -> Dict[str, Any]:
        if path is None or not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return {}

    def _find_previous_artifacts(self, runtime_crc32: str) -> Dict[str, Optional[Path]]:
        out_dir = self.rom_path.parent / "out"
        proof_path = out_dir / f"{runtime_crc32}_proof.json"
        report_json_path = out_dir / f"{runtime_crc32}_reinsertion_report.json"
        report_txt_path = out_dir / f"{runtime_crc32}_report.txt"
        return {
            "proof": proof_path if proof_path.exists() else None,
            "report_json": report_json_path if report_json_path.exists() else None,
            "report_txt": report_txt_path if report_txt_path.exists() else None,
            "out_dir": out_dir if out_dir.exists() else None,
        }

    def _extract_issue_index_from_artifacts(
        self,
        proof_data: Dict[str, Any],
        report_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        index = self._core._empty_issue_index()
        counts = index.get("counts", {})
        examples = index.get("examples", {})
        keys_by_category = index.get("keys_by_category", {})
        seen = {cat: set() for cat in self._core.DELTA_ISSUE_CATEGORIES}

        def _add(cat: str, sample: Dict[str, Any]):
            if cat not in seen or not isinstance(sample, dict):
                return
            key = sample.get("key")
            if key is None:
                return
            key = str(key)
            if key in seen[cat]:
                return
            seen[cat].add(key)
            keys_by_category.setdefault(cat, []).append(key)
            counts[cat] = int(counts.get(cat, 0)) + 1
            if len(examples.setdefault(cat, [])) < 8:
                examples[cat].append({k: v for k, v in sample.items() if v is not None})

        coverage = proof_data.get("coverage", {}) if isinstance(proof_data, dict) else {}
        coverage_samples = coverage.get("samples", {}) if isinstance(coverage, dict) else {}
        for sample in coverage_samples.get("untranslated_same_as_source", []) or []:
            _add("unchanged_equal_src", sample)

        quality_examples = ((proof_data.get("translation_quality", {}) or {}).get("examples", {}) or {})
        for sample in quality_examples.get("non_ptbr_suspect", []) or []:
            _add("suspicious_non_pt", sample)

        evidence_examples = ((proof_data.get("evidence", {}) or {}).get("examples", {}) or {})
        for sample in evidence_examples.get("rom_vs_translated_mismatch", []) or []:
            _add("rom_vs_translated_mismatch", sample)
        for sample in evidence_examples.get("placeholder_fail", []) or []:
            _add("placeholder_fail", sample)
        for sample in evidence_examples.get("terminator_missing", []) or []:
            _add("terminator_missing", sample)

        items = report_data.get("items", []) if isinstance(report_data, dict) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            reason = str(item.get("reason", "")).lower().strip()
            if reason == "token_mismatch":
                _add("placeholder_fail", item)
            elif reason in {"terminator_missing", "terminator_in_payload", "terminator_write_oob"}:
                _add("terminator_missing", item)

        reported_counts = {
            "unchanged_equal_src": int(coverage.get("untranslated_same_as_source", 0) or 0),
            "suspicious_non_pt": int((proof_data.get("translation_quality", {}) or {}).get("non_ptbr_suspect", 0) or 0),
            "rom_vs_translated_mismatch": int((proof_data.get("evidence", {}) or {}).get("rom_vs_translated_mismatch_count", 0) or 0),
            "placeholder_fail": int((proof_data.get("evidence", {}) or {}).get("placeholder_fail_count", 0) or 0),
            "terminator_missing": int((proof_data.get("evidence", {}) or {}).get("terminator_missing_count", 0) or 0),
        }
        for cat in self._core.DELTA_ISSUE_CATEGORIES:
            counts[cat] = max(int(counts.get(cat, 0)), int(reported_counts.get(cat, 0)))
            keys_by_category[cat] = sorted(
                [str(k) for k in keys_by_category.get(cat, [])],
                key=lambda x: (
                    0 if self._core._parse_optional_int_value(x) is not None else 1,
                    self._core._parse_optional_int_value(x)
                    if self._core._parse_optional_int_value(x) is not None
                    else x,
                ),
            )

        all_keys = set()
        for cat in self._core.DELTA_ISSUE_CATEGORIES:
            for key in keys_by_category.get(cat, []):
                all_keys.add(str(key))
        index["total_unique_keys"] = int(len(all_keys))
        return index

    def _prepare_incremental_delta_bundle(
        self,
        translations: Dict[str, str],
        translated_path: Path,
        fallback_meta: Dict[str, Dict[str, Any]],
        mapping_path: Optional[Path],
    ) -> Optional[Dict[str, Any]]:
        """Cria *_delta.jsonl com itens problemáticos e retorna bundle para reinserção."""
        # Delta incremental é modo avançado e opt-in para evitar surpresa em fluxo padrão.
        if os.environ.get("NEUROROM_ENABLE_DELTA", "0") == "0":
            return None
        if translated_path.suffix.lower() != ".jsonl":
            return None
        if translated_path.name.lower().endswith("_delta.jsonl"):
            return None
        if not translations:
            return None

        rom_bytes = self.rom_path.read_bytes()
        runtime_crc32, _ = compute_checksums(rom_bytes)
        runtime_crc32 = str(runtime_crc32).upper()
        runtime_size = len(rom_bytes)

        artifacts = self._find_previous_artifacts(runtime_crc32)
        if not artifacts.get("proof") and not artifacts.get("report_json"):
            return None

        resolved_mapping = mapping_path
        if resolved_mapping is None:
            guessed = self._core._guess_mapping_path(translated_path, self.rom_path)
            resolved_mapping = guessed
        if resolved_mapping is None or not Path(resolved_mapping).exists():
            return None

        self._core.load_mapping(Path(resolved_mapping))
        if not fallback_meta:
            companion_meta, _ = self._load_companion_jsonl_meta(
                translated_path, restrict_keys=set(translations.keys())
            )
            fallback_meta = dict(companion_meta)

        proof_data = self._load_json_safe(artifacts.get("proof"))
        report_data = self._load_json_safe(artifacts.get("report_json"))
        reported_before_issue_index = self._extract_issue_index_from_artifacts(
            proof_data, report_data
        )

        before_issue_index = self._core._build_incremental_issue_index(
            translated=translations,
            fallback_entries=fallback_meta,
            rom_bytes=rom_bytes,
            restrict_keys=set(translations.keys()),
        )
        problem_keys: set = set()
        for cat in self._core.DELTA_ISSUE_CATEGORIES:
            for key in before_issue_index.get("keys_by_category", {}).get(cat, []):
                problem_keys.add(str(key))
            for key in reported_before_issue_index.get("keys_by_category", {}).get(cat, []):
                problem_keys.add(str(key))
        if not problem_keys:
            return None

        rows: List[Dict[str, Any]] = []
        declared_crc32 = self._jsonl_declared_crc32 or runtime_crc32
        declared_size = (
            int(self._jsonl_declared_size)
            if self._jsonl_declared_size is not None
            else int(runtime_size)
        )
        key_reason_map = {
            str(key): sorted(
                [
                    cat
                    for cat in self._core.DELTA_ISSUE_CATEGORIES
                    if (
                        str(key) in set(before_issue_index.get("keys_by_category", {}).get(cat, []))
                        or str(key) in set(reported_before_issue_index.get("keys_by_category", {}).get(cat, []))
                    )
                ]
            )
            for key in problem_keys
        }

        for line in translated_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            if self._core._is_jsonl_meta_record(obj):
                if obj.get("rom_crc32") is not None:
                    declared_crc32 = str(obj.get("rom_crc32")).upper().strip()
                if obj.get("rom_size") is not None:
                    sz = self._core._parse_optional_int_value(obj.get("rom_size"))
                    if sz is not None:
                        declared_size = int(sz)
                continue

            key = self._key_from_obj(obj)
            if key not in problem_keys:
                continue
            text_dst = (
                obj.get("text_dst")
                or obj.get("translation")
                or obj.get("translated_text")
                or obj.get("translated")
                or obj.get("text")
                or translations.get(key)
                or ""
            )
            if not isinstance(text_dst, str) or not text_dst.strip():
                continue
            row = dict(obj)
            row["text_dst"] = str(text_dst)
            meta_obj = fallback_meta.get(key, {})
            if row.get("id") is None and isinstance(meta_obj, dict) and meta_obj.get("id") is not None:
                row["id"] = meta_obj.get("id")
            if row.get("seq") is None and isinstance(meta_obj, dict) and meta_obj.get("seq") is not None:
                row["seq"] = meta_obj.get("seq")
            off_obj = row.get("rom_offset", row.get("offset"))
            if off_obj is None and isinstance(meta_obj, dict):
                off_obj = meta_obj.get("rom_offset", meta_obj.get("offset"))
            off_val = self._core._parse_optional_int_value(off_obj)
            if off_val is not None:
                off_hex = f"0x{int(off_val):06X}"
                row["offset"] = off_hex
                row["rom_offset"] = off_hex
            reasons = key_reason_map.get(key, [])
            if reasons:
                row["delta_reasons"] = reasons
            if declared_crc32:
                row["rom_crc32"] = declared_crc32
            if declared_size is not None:
                row["rom_size"] = int(declared_size)
            rows.append({"key": key, "obj": row})

        if not rows:
            return None

        def _row_sort_key(rec: Dict[str, Any]):
            obj = rec.get("obj", {})
            seq_val = self._core._parse_optional_int_value(obj.get("seq"))
            off_val = self._core._parse_optional_int_value(obj.get("rom_offset", obj.get("offset"))) or 0
            return (
                0 if seq_val is not None else 1,
                seq_val if seq_val is not None else off_val,
                off_val,
                str(rec.get("key", "")),
            )

        rows.sort(key=_row_sort_key)

        delta_path = translated_path.with_name(translated_path.stem + "_delta.jsonl")
        meta_out = {
            "type": "meta",
            "schema": "neurorom.translated_jsonl.delta.v1",
            "rom_crc32": declared_crc32 or runtime_crc32,
            "rom_size": int(declared_size) if declared_size is not None else int(runtime_size),
            "translation_input": str(translated_path.name),
            "ordering": "seq/rom_offset",
            "delta_mode": "incremental",
            "delta_categories": list(self._core.DELTA_ISSUE_CATEGORIES),
            "delta_problem_keys_total": int(len(problem_keys)),
        }
        with open(delta_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(meta_out, ensure_ascii=False) + "\n")
            for rec in rows:
                f.write(json.dumps(rec["obj"], ensure_ascii=False) + "\n")

        delta_translations = self._load_jsonl(delta_path)
        if not delta_translations:
            return None

        return {
            "delta_path": delta_path,
            "translations": delta_translations,
            "fallback_meta": dict(self._jsonl_meta),
            "context": {
                "enabled": True,
                "source_path": str(translated_path),
                "delta_path": str(delta_path),
                "problem_keys_total": int(len(problem_keys)),
                "before_issue_index": before_issue_index,
                "reported_before_issue_index": reported_before_issue_index,
                "runtime_crc32": runtime_crc32,
                "runtime_size": int(runtime_size),
                "artifact_paths": {
                    "proof": str(artifacts.get("proof")) if artifacts.get("proof") else None,
                    "report_json": str(artifacts.get("report_json")) if artifacts.get("report_json") else None,
                    "report_txt": str(artifacts.get("report_txt")) if artifacts.get("report_txt") else None,
                },
            },
        }

    def reinsert(
        self,
        translations: Dict[str, str],
        output_rom_path: str,
        create_backup: bool = True,
        force_blocked: bool = False,
        strict: bool = False,
        dry_run: bool = False,
        report_path: Optional[str] = None,
        mapping_path: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Executa reinserção e retorna (success, message).

        Args:
            force_blocked: Se True, tenta reinserir itens marcados como NOT_PLAUSIBLE_TEXT_SMS
        """
        try:
            translated_path = self._translated_path or self.rom_path
            resolved_mapping = Path(mapping_path) if mapping_path else None
            fallback_meta = dict(self._jsonl_meta)
            delta_context = None

            if translated_path.suffix.lower() == ".jsonl" and translations:
                delta_bundle = self._prepare_incremental_delta_bundle(
                    translations=translations,
                    translated_path=translated_path,
                    fallback_meta=fallback_meta,
                    mapping_path=resolved_mapping,
                )
                if delta_bundle:
                    translated_path = Path(delta_bundle.get("delta_path", translated_path))
                    self._translated_path = translated_path
                    translations = dict(delta_bundle.get("translations", translations))
                    fallback_meta = dict(delta_bundle.get("fallback_meta", fallback_meta))
                    delta_context = dict(delta_bundle.get("context", {}) or {})

            companion_restrict = set(translations.keys()) if delta_context else None
            companion_meta, meta_path = self._load_companion_jsonl_meta(
                translated_path, restrict_keys=companion_restrict
            )
            if companion_meta:
                for key, meta in companion_meta.items():
                    if key in fallback_meta:
                        fallback_meta[key] = self._merge_meta_preserving_binary_fields(
                            meta,
                            fallback_meta[key],
                        )
                    else:
                        fallback_meta[key] = meta
                if meta_path:
                    self._meta_source_path = str(meta_path)
            delta_force_strict = os.environ.get("NEUROROM_DELTA_FORCE_STRICT", "0") == "1"
            strict_run = bool(strict or (delta_context and delta_force_strict))
            out_path, core_stats = self._core.apply_translation(
                rom_path=self.rom_path,
                translated_path=translated_path,
                mapping_path=resolved_mapping,
                output_rom_path=Path(output_rom_path),
                force_blocked=force_blocked,
                translated=translations,
                fallback_entries=(fallback_meta if fallback_meta else None),
                strict=strict_run,
                dry_run=dry_run,
                create_backup=create_backup,
                report_path=(Path(report_path) if report_path else None),
                delta_context=delta_context,
            )
            postpatch_summary: Optional[Dict[str, Any]] = None
            # Pós-patch CRC pode sobrescrever textos já corrigidos em alguns jogos.
            # Mantém desligado por padrão; ativa apenas quando o usuário solicitar.
            postpatch_enabled = os.environ.get("NEUROROM_SMS_POSTPATCH_ENABLE", "0") != "0"
            src_bytes = self.rom_path.read_bytes()
            src_crc32, _ = compute_checksums(src_bytes)
            src_size = len(src_bytes)
            if (
                postpatch_enabled
                and not dry_run
                and apply_sms_post_reinsertion_patches is not None
            ):
                postpatch_profile_path = self._resolve_postpatch_profile_path()
                try:
                    postpatch_summary = apply_sms_post_reinsertion_patches(
                        source_crc32=str(src_crc32).upper(),
                        source_rom_size=int(src_size),
                        output_rom_path=Path(out_path),
                        profile_path=postpatch_profile_path,
                    )
                except PostPatchError as pp_exc:
                    raise ReinsertionError(f"Pos-patch CRC falhou: {pp_exc}") from pp_exc

            # Mapeia stats do core para formato da GUI
            applied_keys = core_stats.get("APPLIED_KEYS")
            if applied_keys is None:
                applied_keys = (
                    core_stats.get("OK", 0)
                    + core_stats.get("REPOINT", 0)
                    + core_stats.get("FORCED", 0)
                    + core_stats.get("REFORM", 0)
                    + core_stats.get("WRAP", 0)
                )
            self.stats["inserted"] = int(applied_keys or 0)
            self.stats["truncated"] = core_stats.get("TRUNC", 0)
            self.stats["skipped"] = core_stats.get(
                "BLOCKED_REAL",
                core_stats.get("BLOCKED", 0) + core_stats.get("SKIP", 0),
            )
            self.stats["forced"] = core_stats.get("FORCED", 0)
            self.stats["structural_skipped"] = core_stats.get(
                "STRUCTURAL_SKIPPED",
                core_stats.get("SKIP", 0),
            )
            self.stats["effective_total"] = core_stats.get(
                "EFFECTIVE_TOTAL_KEYS",
                max(
                    0,
                    int(self.stats.get("inserted", 0))
                    + int(self.stats.get("skipped", 0)),
                ),
            )
            if postpatch_summary and postpatch_summary.get("matched_profile"):
                core_stats["POSTPATCH"] = int(postpatch_summary.get("changed_bytes", 0))
                residual = postpatch_summary.get("residual_english_audit", {})
                if isinstance(residual, dict) and residual.get("enabled"):
                    core_stats["POSTPATCH_RESIDUAL_EN"] = int(residual.get("hits_count", 0))

            msg = f"Reinserção concluída: {out_path}"
            if delta_context:
                msg += f" | delta={delta_context.get('delta_path')}"
            if postpatch_summary and postpatch_summary.get("matched_profile"):
                postpatch_state = (
                    "aplicado" if bool(postpatch_summary.get("changed", False)) else "ok"
                )
                msg += f" | postpatch_crc={postpatch_state}"
                if postpatch_summary.get("proof_path"):
                    msg += f" | proof={postpatch_summary.get('proof_path')}"
                residual = postpatch_summary.get("residual_english_audit", {})
                if isinstance(residual, dict) and residual.get("enabled"):
                    msg += f" | residual_en={int(residual.get('hits_count', 0))}"
                    if residual.get("report_path"):
                        msg += f" | residual_report={residual.get('report_path')}"
            if dry_run:
                msg = f"[DRY-RUN] {msg} (arquivo não escrito)"
            return True, msg

        except ReinsertionError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Erro na reinserção: {e}"

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Decoders por familia de tags (codec/script) para priorizacao de texto legivel.

Meta:
- separar heuristicas por console
- reduzir falso positivo em blobs codificados
- aumentar qualidade dos decoded_candidates
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ICON_RE = re.compile(r"[\U0001F3AE\U0001F50D\U0001F1EF\U0001F1F5]")
HEX_TOKEN_RE = re.compile(r"\[[0-9A-Fa-f]{2}\]")
CTRL_TAG_RE = re.compile(
    r"\[(CMD:[^\]]+|SPEED|WAIT_[^\]]+|NEWLINE|SCROLL|CHOOSE\d*|END|ADDR:[^\]]+|PTR:[^\]]+|Block[^\]]+|[A-Z_]{2,})\]"
)
WORD_RE = re.compile(r"[A-Za-z']+")
SENT_RE = re.compile(r"[A-Za-z][A-Za-z' ,.!?\-]{8,}")

EN_WORDS = set(
    """
the and you your to of in is for with this that from are can be not all one more into over then them if her their
was were will no yes my our out up down just back attack enemy enemies item use name male female world time day warm
breeze personal crisis another options option save load continue start strange lamp houses people have there where what when who
""".split()
)

EN_STRONG = set(
    """
attack enemy enemies options option save load continue start world time name male female
strange lamp houses personal crisis warm breeze another people
""".split()
)


@dataclass
class SegmentResult:
    segment_en: str
    score: int
    details: Dict[str, Any]
    cleaned: str


def infer_console_hint(path_str: str) -> str:
    low = (path_str or "").lower()
    if "\\gba\\" in low or "/gba/" in low:
        return "gba"
    if "playstation 1" in low or "\\ps1\\" in low or "/ps1/" in low:
        return "ps1"
    if "nintedo 64" in low or "nintendo 64" in low:
        return "n64"
    if "super nintedo" in low or "super nintendo" in low:
        return "snes"
    return "generic"


def _extract_crc32_hint(path_str: str) -> Optional[str]:
    """Extrai CRC32 do nome do arquivo/pasta, quando disponível."""
    low_name = Path(path_str or "").name
    m = re.search(r"([A-Fa-f0-9]{8})", low_name)
    if m:
        return m.group(1).upper()
    low_full = str(path_str or "")
    m2 = re.search(r"[\\/](?:[A-Fa-f0-9]{8})[\\/]", low_full)
    if m2:
        token = m2.group(0).strip("\\/").upper()
        if re.fullmatch(r"[A-F0-9]{8}", token):
            return token
    return None


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def candidate_profile_paths(
    pure_jsonl_path: str,
    console_hint: str,
    rom_crc32: Optional[str],
) -> List[Path]:
    """Lista caminhos candidatos para perfil de codec por ROM."""
    p = Path(pure_jsonl_path).expanduser().resolve()
    crc = str(rom_crc32 or _extract_crc32_hint(str(p)) or "").upper()
    if not crc:
        return []
    root = _project_root()
    candidates = [
        p.parent / f"{crc}_codec_profile.json",
        p.parent / "codec_profile.json",
        root / "profiles" / "codec" / console_hint / f"{crc}.json",
        root / "profiles" / "codec" / f"{crc}.json",
    ]
    # Remove duplicados preservando ordem.
    uniq: List[Path] = []
    seen = set()
    for cand in candidates:
        rc = str(cand).lower()
        if rc in seen:
            continue
        seen.add(rc)
        uniq.append(cand)
    return uniq


def load_codec_profile(
    pure_jsonl_path: str,
    console_hint: str,
    rom_crc32: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Carrega perfil de codec aplicável à ROM (se existir)."""
    for path in candidate_profile_paths(pure_jsonl_path, console_hint, rom_crc32):
        if not path.exists():
            continue
        try:
            obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        if obj.get("enabled", True) is False:
            continue
        out = dict(obj)
        out["_path"] = str(path)
        return out
    return None


class BaseTagFamilyDecoder:
    name = "generic_tag_family_v1"

    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        self.profile = dict(profile or {})
        rules = self.profile.get("replace_rules", [])
        self.replace_rules = rules if isinstance(rules, list) else []
        drop_words = self.profile.get("drop_words", [])
        if isinstance(drop_words, list):
            self.drop_words = [str(x).strip() for x in drop_words if str(x).strip()]
        else:
            self.drop_words = []
        min_score = self.profile.get("min_score")
        self.min_score_override = int(min_score) if isinstance(min_score, int) else None

    def _apply_profile_rules(self, text: str) -> str:
        t = text or ""
        for rule in self.replace_rules:
            if not isinstance(rule, dict):
                continue
            src = str(rule.get("src", "")).strip()
            dst = str(rule.get("dst", ""))
            if not src:
                continue
            mode = str(rule.get("mode", "literal")).lower().strip()
            ignore_case = bool(rule.get("ignore_case", False))
            flags = re.IGNORECASE if ignore_case else 0
            try:
                if mode == "regex":
                    t = re.sub(src, dst, t, flags=flags)
                else:
                    # literal com suporte opcional a case-insensitive.
                    if ignore_case:
                        t = re.sub(re.escape(src), dst, t, flags=re.IGNORECASE)
                    else:
                        t = t.replace(src, dst)
            except re.error:
                continue
        for drop in self.drop_words:
            try:
                t = re.sub(rf"\b{re.escape(drop)}\b", " ", t, flags=re.IGNORECASE)
            except re.error:
                continue
        return t

    def preprocess(self, src: str, space_tokens: List[str]) -> str:
        t = ICON_RE.sub(" ", src or "")
        t = CTRL_TAG_RE.sub(" ", t)
        for tok in space_tokens:
            if tok:
                t = t.replace(tok, " ")
        t = self._apply_profile_rules(t)
        t = HEX_TOKEN_RE.sub(" ", t)
        t = t.replace("_", " ")
        t = re.sub(r"[^\x20-\x7E|]+", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def extra_cleanup(self, cleaned: str) -> str:
        t = cleaned
        # Remove blocos longos de codigo alfanumerico.
        t = re.sub(r"\b[A-Z0-9]{5,}\b", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def split_segments(self, cleaned: str) -> List[str]:
        parts: List[str] = []
        parts.extend([p.strip() for p in cleaned.split("|") if p.strip()])
        parts.extend([m.group(0).strip() for m in SENT_RE.finditer(cleaned)])
        # Dedup preservando ordem.
        out: List[str] = []
        seen = set()
        for p in parts:
            if p not in seen:
                seen.add(p)
                out.append(p)
        return out

    def score_segment(self, seg: str) -> Tuple[int, Dict[str, Any]]:
        words = [w.lower() for w in WORD_RE.findall(seg or "")]
        if len(words) < 2:
            return -1, {"words": words}

        recognized = sum(1 for w in words if w in EN_WORDS)
        strong = sum(1 for w in words if w in EN_STRONG)
        ratio = recognized / max(1, len(words))

        alpha_total = max(1, sum(ch.isalpha() for ch in seg))
        details = {
            "words_count": len(words),
            "recognized": recognized,
            "strong": strong,
            "recognized_ratio": ratio,
            "length": len(seg),
            "digit_ratio": sum(ch.isdigit() for ch in seg) / max(1, len(seg)),
            "upper_ratio": sum(ch.isupper() for ch in seg) / alpha_total,
        }

        if len(seg) < 8 or len(seg) > 120:
            return -1, details
        if details["digit_ratio"] > 0.10:
            return -1, details
        if details["upper_ratio"] > 0.45:
            return -1, details
        if recognized < 2:
            return -1, details
        if ratio < 0.50:
            return -1, details
        if strong < 1:
            return -1, details

        score = recognized * 2 + strong * 3 - int((1.0 - ratio) * len(words))
        return score, details

    def threshold(self) -> int:
        if isinstance(self.min_score_override, int):
            return int(self.min_score_override)
        return 7

    def decode_best(self, src: str, space_tokens: List[str]) -> Optional[SegmentResult]:
        cleaned = self.preprocess(src, space_tokens)
        cleaned = self.extra_cleanup(cleaned)
        if not cleaned:
            return None

        best: Optional[SegmentResult] = None
        for seg in self.split_segments(cleaned):
            score, details = self.score_segment(seg)
            if score < self.threshold():
                continue
            row = SegmentResult(
                segment_en=seg,
                score=int(score),
                details=details,
                cleaned=cleaned,
            )
            if best is None or row.score > best.score:
                best = row
        return best


class PS1TagFamilyDecoder(BaseTagFamilyDecoder):
    name = "ps1_tag_family_v1"

    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        super().__init__(profile=profile)

    def extra_cleanup(self, cleaned: str) -> str:
        t = super().extra_cleanup(cleaned)
        # PS1 costuma misturar codigos curtos recorrentes; remove ruido pontual.
        t = re.sub(r"\b(?:nnon|wbo|wbmo|jeb|ebmo)\b", " ", t, flags=re.IGNORECASE)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def threshold(self) -> int:
        return 7


class GBATagFamilyDecoder(BaseTagFamilyDecoder):
    name = "gba_tag_family_v1"
    # Vocabulário enxuto para tentar recuperar palavras úteis de tokens híbridos
    # (ex.: "AoBhow" -> "how", "QaBcome" -> "come").
    KNOWN_FRAGMENTS = [
        "sacred",
        "artifact",
        "currency",
        "people",
        "attack",
        "enemy",
        "enemies",
        "option",
        "options",
        "continue",
        "start",
        "world",
        "there",
        "their",
        "about",
        "which",
        "should",
        "could",
        "would",
        "item",
        "items",
        "magic",
        "power",
        "sword",
        "shield",
        "name",
        "male",
        "female",
        "time",
        "warm",
        "breeze",
        "personal",
        "crisis",
        "another",
        "house",
        "houses",
        "player",
        "level",
        "save",
        "load",
        "menu",
        "there",
        "will",
        "come",
        "your",
        "you",
        "our",
        "them",
        "down",
        "left",
        "right",
        "into",
        "from",
        "with",
        "have",
        "has",
        "are",
        "can",
        "not",
        "who",
        "what",
        "when",
        "where",
        "some",
        "more",
        "one",
        "two",
        "day",
    ]

    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        super().__init__(profile=profile)
        extra = self.profile.get("extra_fragments", [])
        if isinstance(extra, list):
            for item in extra:
                frag = str(item).strip().lower()
                if frag and frag not in self.KNOWN_FRAGMENTS:
                    self.KNOWN_FRAGMENTS.append(frag)

    def _recover_token(self, token: str) -> Optional[str]:
        """Recupera palavra provável a partir de token misto (script+texto)."""
        core = re.sub(r"^[^A-Za-z]+|[^A-Za-z]+$", "", token or "")
        if not core:
            return None
        low = core.lower()
        if low in EN_WORDS:
            return low

        # Prioriza fragmento mais longo encontrado.
        best: Optional[str] = None
        for frag in self.KNOWN_FRAGMENTS:
            pos = low.find(frag)
            if pos < 0:
                continue
            occupy_ratio = len(frag) / max(1, len(low))
            near_end = (pos + len(frag)) >= (len(low) - 1)
            if len(frag) >= 4 and (occupy_ratio >= 0.55 or near_end):
                if best is None or len(frag) > len(best):
                    best = frag
        return best

    def extra_cleanup(self, cleaned: str) -> str:
        t = super().extra_cleanup(cleaned)
        # GBA forense costuma misturar prefixos/sufixos de script nas palavras.
        # Tentamos recuperar somente o núcleo linguístico antes de pontuar candidato.
        recovered: List[str] = []
        for raw in re.split(r"\s+", t):
            if not raw:
                continue
            tok = self._recover_token(raw)
            if tok:
                recovered.append(tok)

        # Segmento recuperado separado por "|" para o split padrão avaliar.
        if len(recovered) >= 4:
            t = f"{t} | {' '.join(recovered)}"

        # Remove tokens muito curtos (normalmente ruído de script nesse console).
        t = re.sub(r"\b[A-Za-z]{1,2}\b", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def score_segment(self, seg: str) -> Tuple[int, Dict[str, Any]]:
        base_score, details = super().score_segment(seg)

        words = [w.lower() for w in WORD_RE.findall(seg or "")]
        recognized = sum(1 for w in words if w in EN_WORDS)
        strong = sum(1 for w in words if w in EN_STRONG)
        ratio = recognized / max(1, len(words))
        long_words = [w for w in words if len(w) >= 5]
        frag_hits = sum(1 for w in words if w in self.KNOWN_FRAGMENTS)

        details["frag_hits"] = frag_hits
        details["long_words"] = len(long_words)
        details["recognized_relaxed"] = recognized
        details["strong_relaxed"] = strong
        details["recognized_ratio_relaxed"] = ratio

        # Caminho estrito (quando o gate base já aprovou).
        if base_score >= 0:
            if frag_hits < 3:
                return -1, details
            if len(long_words) < 2:
                return -1, details
            return base_score + frag_hits, details

        # Caminho relaxado controlado para GBA:
        # aceita segmentos com vocabulário misto (script + texto), mas exige
        # sinais fortes de linguagem real para evitar falso positivo massivo.
        if len(seg or "") < 12 or len(seg or "") > 170:
            return -1, details
        if len(words) < 4:
            return -1, details
        if frag_hits < 4:
            return -1, details
        if recognized < 2:
            return -1, details
        if ratio < 0.32:
            return -1, details
        if details.get("digit_ratio", 0.0) > 0.16:
            return -1, details
        if details.get("upper_ratio", 0.0) > 0.60:
            return -1, details
        # Se não houver palavra forte, exige mais fragmentos confiáveis.
        if strong < 1 and frag_hits < 6:
            return -1, details

        relaxed_score = recognized + (strong * 2) + frag_hits - int((1.0 - ratio) * len(words))
        return int(relaxed_score), details

    def threshold(self) -> int:
        # Ligeiramente menor para permitir recuperação parcial em script híbrido.
        return 6


def get_decoder_for_console(
    console_hint: str,
    profile: Optional[Dict[str, Any]] = None,
) -> BaseTagFamilyDecoder:
    ch = (console_hint or "").lower().strip()
    if ch == "ps1":
        return PS1TagFamilyDecoder(profile=profile)
    if ch == "gba":
        return GBATagFamilyDecoder(profile=profile)
    return BaseTagFamilyDecoder(profile=profile)


def build_decoder_for_input(
    pure_jsonl_path: str,
    console_hint: Optional[str] = None,
    rom_crc32: Optional[str] = None,
) -> Tuple[BaseTagFamilyDecoder, Optional[Dict[str, Any]]]:
    """Monta decoder considerando perfil por ROM (quando houver)."""
    hint = (console_hint or infer_console_hint(pure_jsonl_path) or "generic").lower().strip()
    profile = load_codec_profile(
        pure_jsonl_path=pure_jsonl_path,
        console_hint=hint,
        rom_crc32=rom_crc32,
    )
    decoder = get_decoder_for_console(hint, profile=profile)
    return decoder, profile

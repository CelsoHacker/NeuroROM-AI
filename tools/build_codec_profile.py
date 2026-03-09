#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera perfil de codec por ROM para aumentar cobertura do probe.

Saidas:
- {CRC32}_codec_profile.json
- {CRC32}_codec_profile_report.txt

Uso:
    python build_codec_profile.py --pure-jsonl X_pure_text.jsonl
    python build_codec_profile.py --pure-jsonl X_pure_text.jsonl --install-profile
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from codec_family_decoders import infer_console_hint

ICON_RE = re.compile(r"[\U0001F3AE\U0001F50D\U0001F1EF\U0001F1F5]")
HEX_TOKEN_RE = re.compile(r"\[[0-9A-Fa-f]{2}\]")
CTRL_TAG_RE = re.compile(
    r"\[(CMD:[^\]]+|SPEED|WAIT_[^\]]+|NEWLINE|SCROLL|CHOOSE\d*|END|ADDR:[^\]]+|PTR:[^\]]+|Block[^\]]+|[A-Z_]{2,})\]"
)
WORD_RE = re.compile(r"[A-Za-z]{3,}")
CRC_RE = re.compile(r"([0-9A-Fa-f]{8})")

EN_WORDS = set(
    """
the and you your to of in is for with this that from are can be not all one more into over then them if her their
was were will no yes my our out up down just back attack enemy enemies item use name male female world time day warm
breeze personal crisis another options option save load continue start strange lamp houses people have there where what when who
left right press menu select game player level hp mp power magic sword shield sacred artifact currency
""".split()
)

SEED_FRAGMENTS = [
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


def iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


def infer_crc_from_jsonl_path(path: Path) -> Optional[str]:
    name = path.name
    m = CRC_RE.search(name)
    if m:
        return str(m.group(1)).upper()
    return None


def infer_rom_size_from_manifest(pure_jsonl: Path) -> Optional[int]:
    # Estrutura esperada: <console>/<CRC32>/1_extracao/<CRC32>_pure_text.jsonl
    try:
        crc_dir = pure_jsonl.parent.parent
        manifest = crc_dir / "crc_bootstrap_manifest.json"
        if manifest.exists():
            obj = json.loads(manifest.read_text(encoding="utf-8", errors="replace"))
            if isinstance(obj, dict):
                val = obj.get("rom_size")
                if isinstance(val, int):
                    return int(val)
                if isinstance(val, float):
                    return int(val)
                if isinstance(val, str) and val.strip().isdigit():
                    return int(val.strip())
    except Exception:
        return None
    return None


def clean_text(src: str) -> str:
    t = ICON_RE.sub(" ", src or "")
    t = CTRL_TAG_RE.sub(" ", t)
    t = HEX_TOKEN_RE.sub(" ", t)
    t = t.replace("_", " ")
    t = re.sub(r"[^\x20-\x7E|]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def best_fragment(token: str, fragments: List[str]) -> Optional[str]:
    low = token.lower()
    if low in EN_WORDS:
        return None
    best: Optional[Tuple[float, str]] = None
    for frag in fragments:
        pos = low.find(frag)
        if pos < 0:
            continue
        ratio = len(frag) / max(1, len(low))
        near_end = (pos + len(frag)) >= (len(low) - 1)
        score = ratio + (0.15 if near_end else 0.0) + (0.02 * len(frag))
        if len(frag) >= 3 and (ratio >= 0.45 or near_end):
            if best is None or score > best[0]:
                best = (score, frag)
    return best[1] if best else None


def derive_profile(
    pure_jsonl: Path,
    console_hint: str,
    min_hits: int,
    max_rules: int,
) -> Dict[str, Any]:
    meta: Dict[str, Any] = {}
    fallback_crc: Optional[str] = None
    fallback_size: Optional[int] = None
    token_counter: Counter[str] = Counter()
    map_counter: Counter[Tuple[str, str]] = Counter()
    frag_counter: Counter[str] = Counter()
    items_total = 0
    rows_with_text = 0

    for obj in iter_jsonl(pure_jsonl):
        if obj.get("type") == "meta":
            meta = obj
            continue
        if fallback_crc is None and obj.get("rom_crc32"):
            fallback_crc = str(obj.get("rom_crc32")).upper()
        if fallback_size is None and obj.get("rom_size") is not None:
            try:
                fallback_size = int(obj.get("rom_size"))
            except Exception:
                fallback_size = None
        items_total += 1
        src = str(obj.get("text_src", ""))
        cleaned = clean_text(src)
        if not cleaned:
            continue
        rows_with_text += 1
        for tok in WORD_RE.findall(cleaned):
            low = tok.lower()
            token_counter[low] += 1
            if low in EN_WORDS:
                continue
            frag = best_fragment(low, SEED_FRAGMENTS)
            if frag and frag != low:
                map_counter[(low, frag)] += 1
                frag_counter[frag] += 1

    replace_rules: List[Dict[str, Any]] = []
    for (src_tok, dst_tok), cnt in map_counter.most_common(max_rules * 3):
        if cnt < min_hits:
            continue
        # Evita regras fracas.
        if len(dst_tok) < 3:
            continue
        replace_rules.append(
            {
                "mode": "regex",
                "src": rf"\b{re.escape(src_tok)}\b",
                "dst": dst_tok,
                "ignore_case": True,
                "hits": int(cnt),
            }
        )
        if len(replace_rules) >= max_rules:
            break

    vowels = set("aeiou")
    drop_words: List[str] = []
    for tok, cnt in token_counter.most_common(500):
        if cnt < max(min_hits, 6):
            continue
        if tok in EN_WORDS:
            continue
        if len(tok) < 4:
            continue
        vowel_ratio = sum(1 for ch in tok if ch in vowels) / max(1, len(tok))
        if vowel_ratio < 0.2:
            drop_words.append(tok)
        if len(drop_words) >= 60:
            break

    extra_fragments = [frag for frag, cnt in frag_counter.most_common(80) if cnt >= min_hits]

    rom_crc32 = str(meta.get("rom_crc32") or "").upper() or fallback_crc or infer_crc_from_jsonl_path(pure_jsonl)
    rom_size = meta.get("rom_size")
    if rom_size is None:
        rom_size = fallback_size
    if rom_size is None:
        rom_size = infer_rom_size_from_manifest(pure_jsonl)

    profile = {
        "schema": "neurorom.codec_profile.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "enabled": True,
        "console_hint": console_hint,
        "rom_crc32": rom_crc32 or None,
        "rom_size": rom_size,
        "source_pure_jsonl": str(pure_jsonl),
        "min_score": None,
        "replace_rules": replace_rules,
        "drop_words": drop_words,
        "extra_fragments": extra_fragments,
        "stats": {
            "items_total": int(items_total),
            "rows_with_text": int(rows_with_text),
            "unique_tokens": int(len(token_counter)),
            "replace_rules_total": int(len(replace_rules)),
            "drop_words_total": int(len(drop_words)),
            "extra_fragments_total": int(len(extra_fragments)),
        },
    }
    return profile


def default_paths(
    pure_jsonl: Path,
    profile: Dict[str, Any],
    out_profile: Optional[str],
    out_report: Optional[str],
) -> Tuple[Path, Path]:
    crc = str(profile.get("rom_crc32") or "UNKNOWN").upper()
    p_profile = (
        Path(out_profile).expanduser().resolve()
        if out_profile
        else pure_jsonl.parent / f"{crc}_codec_profile.json"
    )
    p_report = (
        Path(out_report).expanduser().resolve()
        if out_report
        else pure_jsonl.parent / f"{crc}_codec_profile_report.txt"
    )
    return p_profile, p_report


def install_profile(profile_path: Path, console_hint: str, rom_crc32: Optional[str]) -> Optional[Path]:
    if not rom_crc32:
        return None
    root = Path(__file__).resolve().parents[1]
    target = root / "profiles" / "codec" / console_hint / f"{rom_crc32}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(profile_path.read_text(encoding="utf-8"), encoding="utf-8")
    return target


def write_report(report_path: Path, profile_path: Path, profile: Dict[str, Any], install_path: Optional[Path]) -> None:
    stats = profile.get("stats", {}) if isinstance(profile, dict) else {}
    lines = [
        "CODEC PROFILE BUILDER",
        f"generated_at={profile.get('generated_at')}",
        f"profile_path={profile_path}",
        f"console_hint={profile.get('console_hint')}",
        f"rom_crc32={profile.get('rom_crc32')}",
        f"rom_size={profile.get('rom_size')}",
        f"source_pure_jsonl={profile.get('source_pure_jsonl')}",
        "",
        "STATS:",
        f"  items_total={stats.get('items_total', 0)}",
        f"  rows_with_text={stats.get('rows_with_text', 0)}",
        f"  unique_tokens={stats.get('unique_tokens', 0)}",
        f"  replace_rules_total={stats.get('replace_rules_total', 0)}",
        f"  drop_words_total={stats.get('drop_words_total', 0)}",
        f"  extra_fragments_total={stats.get('extra_fragments_total', 0)}",
    ]
    if install_path is not None:
        lines.extend(["", f"INSTALLED_PROFILE={install_path}"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Gera perfil de codec por ROM para melhorar probe/decoder.")
    ap.add_argument("--pure-jsonl", required=True, help="Arquivo {CRC32}_pure_text.jsonl")
    ap.add_argument("--console-hint", default=None, help="Forca console_hint (opcional)")
    ap.add_argument("--out-profile", default=None, help="Caminho de saida para perfil JSON")
    ap.add_argument("--out-report", default=None, help="Caminho de saida para relatorio TXT")
    ap.add_argument("--min-hits", type=int, default=4, help="Minimo de ocorrencias para regra")
    ap.add_argument("--max-rules", type=int, default=120, help="Maximo de regras no perfil")
    ap.add_argument(
        "--install-profile",
        action="store_true",
        help="Instala perfil em profiles/codec/<console>/<crc>.json",
    )
    args = ap.parse_args()

    pure_jsonl = Path(args.pure_jsonl).expanduser().resolve()
    if not pure_jsonl.exists():
        raise SystemExit(f"[ERRO] pure-jsonl nao encontrado: {pure_jsonl}")

    console_hint = str(args.console_hint or infer_console_hint(str(pure_jsonl)) or "generic").lower()
    profile = derive_profile(
        pure_jsonl=pure_jsonl,
        console_hint=console_hint,
        min_hits=max(1, int(args.min_hits)),
        max_rules=max(1, int(args.max_rules)),
    )

    profile_path, report_path = default_paths(
        pure_jsonl=pure_jsonl,
        profile=profile,
        out_profile=args.out_profile,
        out_report=args.out_report,
    )
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

    install_path = None
    if args.install_profile:
        install_path = install_profile(
            profile_path=profile_path,
            console_hint=console_hint,
            rom_crc32=profile.get("rom_crc32"),
        )

    write_report(
        report_path=report_path,
        profile_path=profile_path,
        profile=profile,
        install_path=install_path,
    )

    print(f"[OK] profile={profile_path}")
    print(f"[OK] report={report_path}")
    if install_path is not None:
        print(f"[OK] installed={install_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

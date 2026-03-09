# -*- coding: utf-8 -*-
"""
Auditor automatico de pureza textual para artefatos de extracao.

Suposicoes minimas:
1) Entrada principal no formato "[0xOFFSET] texto" (arquivo by_offset existente).
2) Nao cria formato novo de metadado; apenas gera relatorios auxiliares por CRC.
3) Usa heuristicas de plausibilidade existentes (core.plausibility) como base.
4) Correcao automatica atua apenas no artefato de traducao (nao altera mapping).
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
from collections import Counter
from typing import Any

try:
    from .plausibility import classify_human_candidate, normalize_human_text
except Exception:  # pragma: no cover - fallback para execucao direta
    from plausibility import classify_human_candidate, normalize_human_text


_LINE_WITH_OFFSET_RE = re.compile(r"^\[(0x[0-9A-Fa-f]+)\]\s*(.*)$")
_CTRL_RE = re.compile(r"[\x00-\x1F\x7F-\x9F]")
_DOT_COMPOUND_RE = re.compile(r"^[A-Za-z]{2,6}\.[A-Za-z]{2,8}$")
_SINGLE_PREFIX_RE = re.compile(r"^[A-Za-z]\s+[A-Za-z]{3,}$")
_COMPACT_UPPER_RE = re.compile(r"^[A-Z]{3,6}$")
_ALL_CAPS_WORD_RE = re.compile(r"^[A-Z]{3,10}$")
_SPACED_SINGLE_LETTERS_RE = re.compile(r"^[A-Za-z](?:\s+[A-Za-z])+$")
_TRAILING_SINGLE_LETTER_RE = re.compile(r"^[A-Za-z]{2,}\s+[A-Za-z]$")
_LEADING_SYMBOL_WORD_RE = re.compile(r"^[^A-Za-z0-9\s][A-Za-z]{4,}$")
_INTERNAL_SYMBOL_WORD_RE = re.compile(r"[A-Za-z][!?:;][A-Za-z]")
_SPACES_RE = re.compile(r"\s+")
_SHORT_CAPS_WHITELIST = {
    "HP",
    "MP",
    "XP",
    "GP",
    "YES",
    "NO",
    "END",
    "NAME",
    "JOIN",
    "GIVE",
    "SHOP",
    "BUY",
    "SELL",
    "INN",
}
_TECH_PREFIX_CHARS = {"T", "Z", "z", "h", "i", "v", "V", "&", "4", "=", "{"}
_ALLOWED_TEXT_CHARS_RE = re.compile(r"^[A-Za-z0-9 '\-\.,!?:;\"()/]+$")


def _parse_offset(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            if s.lower().startswith("0x"):
                return int(s, 16)
            return int(s, 10)
        except ValueError:
            return None
    return None


def _sanitize_for_report(text: str) -> str:
    compact = _SPACES_RE.sub(" ", str(text or "")).strip()
    return compact[:220]


def _is_alpha_byte(value: int) -> bool:
    return (0x41 <= int(value) <= 0x5A) or (0x61 <= int(value) <= 0x7A)


def _is_printable_ascii_byte(value: int) -> bool:
    return 0x20 <= int(value) <= 0x7E


def _text_quality_score(text: str) -> int:
    t = str(text or "").strip()
    if not t:
        return -999
    letters = sum(1 for c in t if c.isalpha())
    vowels = sum(1 for c in t.lower() if c in "aeiou")
    spaces = sum(1 for c in t if c.isspace())
    digits = sum(1 for c in t if c.isdigit())
    punct = sum(1 for c in t if c in ".,!?:;'\"-()/")
    weird = sum(
        1 for c in t if (not c.isalnum()) and (not c.isspace()) and c not in ".,!?:;'\"-()/"
    )
    score = (letters * 4) + (vowels * 2) + spaces + punct - (digits * 2) - (weird * 8)
    if t and t[0].islower():
        score -= 5
    return int(score)


def _looks_fragment_head(text: str) -> bool:
    t = str(text or "").strip()
    if not t or not t[:1].isalpha():
        return False
    if t[0].islower():
        return True

    alpha_tokens = [tok for tok in re.findall(r"[A-Za-z]+", t) if tok]
    if not alpha_tokens:
        return False

    letters_only = "".join(alpha_tokens)
    vowels = sum(1 for c in letters_only.lower() if c in "aeiou")

    if t.upper() == t:
        if len(letters_only) <= 5:
            return True
        if vowels <= 1:
            return True
        if len(alpha_tokens) >= 2 and len(alpha_tokens[0]) <= 3 and len(alpha_tokens[1]) >= 4:
            return True

    if len(alpha_tokens) >= 2 and len(alpha_tokens[0]) <= 2 and len(alpha_tokens[1]) >= 4:
        return True

    return False


def _read_full_ascii_candidate(rom_data: bytes, start: int, max_len: int = 120) -> str:
    if start < 0 or start >= len(rom_data):
        return ""
    out = bytearray()
    i = int(start)
    while i < len(rom_data) and len(out) < int(max_len):
        b = int(rom_data[i])
        if b in (0x00, 0x01):
            break
        if not _is_printable_ascii_byte(b):
            break
        out.append(b)
        i += 1
    if not out:
        return ""
    return out.decode("ascii", errors="ignore")


def _try_repair_prefix_fragment(
    text: str,
    offset: int | None,
    rom_data: bytes | None,
) -> tuple[str, str | None]:
    """
    Corrige fragmentos comuns de ponteiro-sufixo.
    Retorna (texto_final, motivo):
      - motivo="prefix_fragment_repaired" quando corrigido
      - motivo="prefix_fragment_unresolved" quando detectado, mas inseguro para corrigir
      - motivo=None quando não aplicável
    """
    current = str(text or "").strip()
    if not current or not isinstance(offset, int) or rom_data is None:
        return current, None
    if offset <= 0 or offset >= len(rom_data):
        return current, None
    if not current[:1].isalpha():
        return current, None

    prev = int(rom_data[offset - 1])
    if not _is_alpha_byte(prev):
        return current, None

    start = int(offset)
    while start > 0 and _is_alpha_byte(int(rom_data[start - 1])) and (offset - start) < 6:
        start -= 1

    prefix_len = int(offset - start)
    if prefix_len <= 0 or prefix_len > 6:
        return current, None

    full_raw = _read_full_ascii_candidate(rom_data, start)
    if not full_raw:
        return current, None
    full_norm = normalize_human_text(full_raw)
    if not full_norm or full_norm == current:
        return current, None

    suspicious = _looks_fragment_head(current)
    leading_symbol_fragment = bool(
        len(current) >= 2 and (not current[0].isalnum()) and current[1].isalpha()
    )
    is_fragment_like = bool(suspicious or leading_symbol_fragment)

    ok_full, _reason_full = classify_human_candidate(full_norm, source="POINTER")
    if not ok_full:
        return current, "prefix_fragment_unresolved" if is_fragment_like else None

    prefix_raw = full_raw[:prefix_len] if prefix_len <= len(full_raw) else ""
    if prefix_len == 1 and prefix_raw in _TECH_PREFIX_CHARS:
        return current, "prefix_fragment_unresolved" if is_fragment_like else None

    if not _ALLOWED_TEXT_CHARS_RE.fullmatch(full_norm):
        return current, "prefix_fragment_unresolved" if is_fragment_like else None

    score_current = _text_quality_score(current)
    score_full = _text_quality_score(full_norm)
    upper_pair_safe = (
        current.upper() == current
        and full_norm.upper() == full_norm
        and 1 <= prefix_len <= 2
        and len(current) >= 6
        and len(full_norm) <= (len(current) + 2)
    )
    suffix_match_safe = (
        current.upper() == current
        and full_norm.upper() == full_norm
        and 1 <= prefix_len <= 4
        and full_norm.endswith(current)
        and len(full_norm) <= (len(current) + 4)
    )
    if score_full >= (score_current + 2) and (is_fragment_like or upper_pair_safe or suffix_match_safe):
        return full_norm, "prefix_fragment_repaired"

    return current, "prefix_fragment_unresolved" if is_fragment_like else None


def _load_rom_bytes(rom_path: str | None) -> bytes | None:
    path = str(rom_path or "").strip()
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            return f.read()
    except Exception:
        return None


def _classify_extra_suspect(text: str) -> str | None:
    """
    Heuristicas adicionais leves para marcar linhas duvidosas.
    Nao marca como erro direto para evitar perda agressiva.
    """
    t = str(text or "").strip()
    if not t:
        return "empty"

    if _LEADING_SYMBOL_WORD_RE.fullmatch(t):
        return "leading_symbol_fragment"

    if _INTERNAL_SYMBOL_WORD_RE.search(t):
        return "internal_symbol_fragment"

    if _DOT_COMPOUND_RE.fullmatch(t):
        # Abreviações legítimas de RPG (ex.: Chn.Mail, Mys.Robe, Bk.pearl, Nt.shade).
        # Se ambos lados do ponto têm >= 2 chars, é padrão de item abreviado, não lixo.
        return None

    if _SINGLE_PREFIX_RE.fullmatch(t):
        # Artigo inglês "a" + substantivo é legítimo (ex.: a guard, a child, a fighter).
        first_char = t[0].lower()
        if first_char in {"a", "i"}:
            return None
        return "single_letter_prefix"

    if re.match(r"^[A-Za-z]\s", t):
        alpha_words = re.findall(r"[A-Za-z]+", t)
        if len(alpha_words) >= 3 and len(alpha_words[0]) == 1:
            head = alpha_words[0].lower()
            if head not in {"a", "i", "o", "e"}:
                return "single_letter_prefix_fragment"

    if _SPACED_SINGLE_LETTERS_RE.fullmatch(t):
        return "spaced_single_letters"

    if _TRAILING_SINGLE_LETTER_RE.fullmatch(t):
        # Nomes de magia/item com stat suffix (ex.: "Sling F", "Staff A").
        # Se a primeira palavra tem >= 3 chars e a letra final é A-F, é legítimo.
        parts = t.split()
        if len(parts) == 2 and len(parts[0]) >= 3 and parts[1].upper() in "ABCDEF":
            return None
        return "trailing_single_letter"

    if _COMPACT_UPPER_RE.fullmatch(t):
        vowels = sum(1 for ch in t if ch in "AEIOU")
        if vowels <= 1:
            return "compact_upper_token"

    if _ALL_CAPS_WORD_RE.fullmatch(t):
        if len(t) <= 4 and t not in _SHORT_CAPS_WHITELIST:
            return "short_all_caps_word"

    # Tokens aleatórios mistos (ex.: XIYiJZj): alternância de caixa alta/baixa
    # com poucas vogais tende a ser ruído de decodificação.
    if t.isalpha() and " " not in t and len(t) >= 6:
        has_upper = any(ch.isupper() for ch in t)
        has_lower = any(ch.islower() for ch in t)
        if has_upper and has_lower:
            vowels = sum(1 for ch in t.lower() if ch in "aeiou")
            case_changes = sum(
                1 for a, b in zip(t, t[1:]) if (a.isupper() != b.isupper())
            )
            if vowels <= 2 and case_changes >= 3:
                return "mixed_case_gibberish"

    # Matriz de tokens em maiúsculas com letras soltas (ex.: FIREBALL A F, AB E)
    # é típica de lixo de tabela, não texto fluido para tradução.
    # Exceção: nomes de magia/habilidade com stat codes (ex.: FIREBALL A F, MAGIC MISSILE A F)
    # onde a primeira palavra é um nome real (>= 5 chars).
    words = [w for w in t.split() if w]
    if len(words) >= 2 and all(w.isalpha() for w in words):
        if all(w.upper() == w for w in words):
            single_count = sum(1 for w in words if len(w) == 1)
            if single_count >= 2:
                multi_words = [w for w in words if len(w) >= 3]
                if multi_words and len(multi_words[0]) >= 5:
                    return None  # Nome real + stat codes (FIREBALL A F)
                return "upper_token_matrix"

    return None


@dataclass
class AuditEntry:
    line_no: int
    offset: int | None
    raw_text: str
    normalized_text: str
    status: str
    reason: str
    corrected: bool


class AutoTextAuditor:
    def __init__(
        self,
        purity_min_score: int = 98,
        keep_suspects: bool = False,
        fail_on_suspect: bool = True,
    ) -> None:
        self.purity_min_score = max(0, min(100, int(purity_min_score)))
        self.keep_suspects = bool(keep_suspects)
        self.fail_on_suspect = bool(fail_on_suspect)

    def audit(
        self,
        by_offset_path: str,
        stage_dir: str,
        crc32: str,
        output_path: str | None = None,
        rom_path: str | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "enabled": True,
            "input_by_offset_path": by_offset_path,
            "pure_path": None,
            "report_json_path": None,
            "report_txt_path": None,
            "suspects_path": None,
            "errors_path": None,
            "total": 0,
            "ok": 0,
            "suspect": 0,
            "error": 0,
            "corrected": 0,
            "prefix_repaired": 0,
            "prefix_suspect": 0,
            "duplicate_text_removed": 0,
            "pure_lines": 0,
            "kept_suspects": bool(self.keep_suspects),
            "purity_score": 0,
            "purity_min_score": int(self.purity_min_score),
            "fail_on_suspect": bool(self.fail_on_suspect),
            "passed": False,
            "fail_reason": "",
            "reason_counts": {},
        }
        if not by_offset_path or not os.path.exists(by_offset_path):
            result["passed"] = False
            return result
        if not stage_dir:
            stage_dir = os.path.dirname(by_offset_path)
        os.makedirs(stage_dir, exist_ok=True)
        rom_data = _load_rom_bytes(rom_path)

        entries: list[AuditEntry] = []
        try:
            with open(by_offset_path, "r", encoding="utf-8", errors="replace") as f:
                for line_no, raw_line in enumerate(f, start=1):
                    line = raw_line.rstrip("\r\n")
                    if not line.strip():
                        continue
                    offset = None
                    text = line.strip()
                    m = _LINE_WITH_OFFSET_RE.match(line)
                    if m:
                        offset = _parse_offset(m.group(1))
                        text = m.group(2)
                    raw_text = str(text or "")
                    normalized = normalize_human_text(raw_text)
                    corrected = normalized != raw_text
                    prefix_reason: str | None = None
                    if rom_data is not None:
                        repaired_text, prefix_reason = _try_repair_prefix_fragment(
                            normalized,
                            offset,
                            rom_data,
                        )
                        if repaired_text != normalized:
                            corrected = True
                            normalized = repaired_text
                    if prefix_reason == "prefix_fragment_unresolved":
                        entries.append(
                            AuditEntry(
                                line_no=line_no,
                                offset=offset,
                                raw_text=raw_text,
                                normalized_text=normalized,
                                status="suspect",
                                reason="prefix_fragment_unresolved",
                                corrected=corrected,
                            )
                        )
                        continue

                    if not normalized:
                        entries.append(
                            AuditEntry(
                                line_no=line_no,
                                offset=offset,
                                raw_text=raw_text,
                                normalized_text="",
                                status="error",
                                reason="empty_after_normalize",
                                corrected=corrected,
                            )
                        )
                        continue

                    if _CTRL_RE.search(normalized):
                        entries.append(
                            AuditEntry(
                                line_no=line_no,
                                offset=offset,
                                raw_text=raw_text,
                                normalized_text=normalized,
                                status="error",
                                reason="control_chars",
                                corrected=corrected,
                            )
                        )
                        continue

                    ok, reason = classify_human_candidate(normalized, source="POINTER")
                    if not ok:
                        entries.append(
                            AuditEntry(
                                line_no=line_no,
                                offset=offset,
                                raw_text=raw_text,
                                normalized_text=normalized,
                                status="error",
                                reason=str(reason or "not_human"),
                                corrected=corrected,
                            )
                        )
                        continue

                    suspect_reason = _classify_extra_suspect(normalized)
                    if suspect_reason:
                        entries.append(
                            AuditEntry(
                                line_no=line_no,
                                offset=offset,
                                raw_text=raw_text,
                                normalized_text=normalized,
                                status="suspect",
                                reason=suspect_reason,
                                corrected=corrected,
                            )
                        )
                        continue

                    entries.append(
                        AuditEntry(
                            line_no=line_no,
                            offset=offset,
                            raw_text=raw_text,
                            normalized_text=normalized,
                            status="ok",
                            reason="prefix_fragment_repaired"
                            if prefix_reason == "prefix_fragment_repaired"
                            else "ok",
                            corrected=corrected,
                        )
                    )
        except Exception:
            result["passed"] = False
            return result

        total = len(entries)

        # Segunda passada: detecta fragmentos em caixa alta que sao subparte
        # de palavra maior presente no mesmo conjunto (ex.: OFFREY vs GEOFFREY).
        caps_words = [
            (idx, e.normalized_text)
            for idx, e in enumerate(entries)
            if e.status == "ok" and _ALL_CAPS_WORD_RE.fullmatch(e.normalized_text)
        ]
        if caps_words:
            all_caps_texts = [txt for _, txt in caps_words]
            for idx, txt in caps_words:
                if len(txt) < 5:
                    continue
                for other in all_caps_texts:
                    if other == txt:
                        continue
                    if txt in other and 1 <= (len(other) - len(txt)) <= 2:
                        e = entries[idx]
                        entries[idx] = AuditEntry(
                            line_no=e.line_no,
                            offset=e.offset,
                            raw_text=e.raw_text,
                            normalized_text=e.normalized_text,
                            status="suspect",
                            reason="fragment_of_longer_word",
                            corrected=e.corrected,
                        )
                        break

        total = len(entries)
        ok_count = sum(1 for e in entries if e.status == "ok")
        suspect_count = sum(1 for e in entries if e.status == "suspect")
        error_count = sum(1 for e in entries if e.status == "error")
        corrected_count = sum(1 for e in entries if e.corrected)
        prefix_repaired_count = sum(
            1 for e in entries if e.reason == "prefix_fragment_repaired"
        )
        prefix_suspect_count = sum(
            1 for e in entries if e.reason == "prefix_fragment_unresolved"
        )

        kept_entries: list[AuditEntry] = []
        for e in entries:
            if e.status == "ok":
                kept_entries.append(e)
            elif e.status == "suspect" and self.keep_suspects:
                kept_entries.append(e)

        seen_texts: set[str] = set()
        pure_lines: list[str] = []
        duplicate_text_removed = 0
        for e in kept_entries:
            txt = e.normalized_text.strip()
            if not txt:
                continue
            dedup_key = txt.casefold()
            if dedup_key in seen_texts:
                duplicate_text_removed += 1
                continue
            seen_texts.add(dedup_key)
            pure_lines.append(txt)

        penalty = float(error_count) + (0.35 * float(suspect_count))
        if total <= 0:
            score = 0
        else:
            score = int(round(max(0.0, 100.0 * (1.0 - (penalty / float(total))))))
        fail_reason = ""
        if error_count > 0:
            fail_reason = "errors_present"
        elif self.fail_on_suspect and suspect_count > 0:
            fail_reason = "suspects_present"
        elif score < self.purity_min_score:
            fail_reason = "score_below_threshold"
        passed = bool(not fail_reason)

        reason_counts = Counter(e.reason for e in entries)

        pure_path = (
            str(output_path).strip()
            if output_path and str(output_path).strip()
            else os.path.join(stage_dir, f"{crc32}_only_safe_text_pure.txt")
        )
        suspects_path = os.path.join(stage_dir, f"{crc32}_auto_audit_suspects.txt")
        errors_path = os.path.join(stage_dir, f"{crc32}_auto_audit_errors.txt")
        report_json_path = os.path.join(stage_dir, f"{crc32}_auto_audit_report.json")
        report_txt_path = os.path.join(stage_dir, f"{crc32}_auto_audit_report.txt")

        try:
            with open(pure_path, "w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(pure_lines))
            with open(suspects_path, "w", encoding="utf-8", newline="\n") as f:
                for e in entries:
                    if e.status != "suspect":
                        continue
                    off = f"0x{e.offset:06X}" if isinstance(e.offset, int) else "N/A"
                    f.write(
                        f"[{off}] reason={e.reason} | text={_sanitize_for_report(e.normalized_text)}\n"
                    )
            with open(errors_path, "w", encoding="utf-8", newline="\n") as f:
                for e in entries:
                    if e.status != "error":
                        continue
                    off = f"0x{e.offset:06X}" if isinstance(e.offset, int) else "N/A"
                    f.write(
                        f"[{off}] reason={e.reason} | text={_sanitize_for_report(e.normalized_text or e.raw_text)}\n"
                    )

            payload = {
                "schema": "neurorom.auto_text_audit.v1",
                "crc32": str(crc32 or "").upper(),
                "input_by_offset_path": by_offset_path,
                "pure_path": pure_path,
                "suspects_path": suspects_path,
                "errors_path": errors_path,
                "summary": {
                    "total": int(total),
                    "ok": int(ok_count),
                    "suspect": int(suspect_count),
                    "error": int(error_count),
                    "corrected": int(corrected_count),
                    "prefix_repaired": int(prefix_repaired_count),
                    "prefix_suspect": int(prefix_suspect_count),
                    "duplicate_text_removed": int(duplicate_text_removed),
                    "pure_lines": int(len(pure_lines)),
                    "keep_suspects": bool(self.keep_suspects),
                    "fail_on_suspect": bool(self.fail_on_suspect),
                    "purity_score": int(score),
                    "purity_min_score": int(self.purity_min_score),
                    "passed": bool(passed),
                    "fail_reason": str(fail_reason),
                },
                "reason_counts": {str(k): int(v) for k, v in sorted(reason_counts.items())},
            }
            with open(report_json_path, "w", encoding="utf-8", newline="\n") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

            with open(report_txt_path, "w", encoding="utf-8", newline="\n") as f:
                f.write("AUTO TEXT AUDIT REPORT\n")
                f.write(f"crc32={str(crc32 or '').upper()}\n")
                f.write(f"input_by_offset={by_offset_path}\n")
                f.write(f"pure_path={pure_path}\n")
                f.write(f"suspects_path={suspects_path}\n")
                f.write(f"errors_path={errors_path}\n")
                f.write(
                    "summary: "
                    f"total={total} ok={ok_count} suspect={suspect_count} error={error_count} "
                    f"corrected={corrected_count} duplicate_text_removed={duplicate_text_removed} "
                    f"prefix_repaired={prefix_repaired_count} prefix_suspect={prefix_suspect_count} "
                    f"pure_lines={len(pure_lines)} keep_suspects={str(self.keep_suspects).lower()} "
                    f"fail_on_suspect={str(self.fail_on_suspect).lower()} "
                    f"purity_score={score} min_score={self.purity_min_score} "
                    f"passed={str(passed).lower()} fail_reason={fail_reason or 'none'}\n"
                )
                f.write("reason_counts:\n")
                for reason, count in sorted(reason_counts.items(), key=lambda it: (-int(it[1]), str(it[0]))):
                    f.write(f"  - {reason}: {int(count)}\n")

        except Exception:
            result["passed"] = False
            return result

        result.update(
            {
                "pure_path": pure_path,
                "report_json_path": report_json_path,
                "report_txt_path": report_txt_path,
                "suspects_path": suspects_path,
                "errors_path": errors_path,
                "total": int(total),
                "ok": int(ok_count),
                "suspect": int(suspect_count),
                "error": int(error_count),
                "corrected": int(corrected_count),
                "prefix_repaired": int(prefix_repaired_count),
                "prefix_suspect": int(prefix_suspect_count),
                "duplicate_text_removed": int(duplicate_text_removed),
                "pure_lines": int(len(pure_lines)),
                "purity_score": int(score),
                "fail_on_suspect": bool(self.fail_on_suspect),
                "passed": bool(passed),
                "fail_reason": str(fail_reason),
                "reason_counts": {str(k): int(v) for k, v in sorted(reason_counts.items())},
            }
        )
        return result
